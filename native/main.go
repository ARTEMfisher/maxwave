// MaxWave's controller lives on the Station. Desktop tools only install and inspect it.
package main

import (
	"bufio"
	"context"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

var root = flag.String("dir", "/data/local/tmp/maxwave-native", "installation directory")
var observe = flag.Bool("observe", false, "observe without routing")
var resolve = flag.String("resolve", "", "resolve JSON intent (network child)")

type peer struct {
	conn net.Conn
	mu   sync.Mutex
}

func (p *peer) send(v any) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.conn.SetWriteDeadline(time.Now().Add(2 * time.Second))
	return json.NewEncoder(p.conn).Encode(v)
}

type controller struct {
	mu      sync.Mutex
	peers   map[string]*peer
	cancel  context.CancelFunc
	request string
	call    uint64
	pending map[uint64]chan obj
	token   string
	ctx     context.Context
}

func (c *controller) rpc(role, method string, args ...any) {
	c.mu.Lock()
	p := c.peers[role]
	c.call++
	id := c.call
	c.mu.Unlock()
	if p != nil {
		if err := p.send(obj{"method": method, "args": args, "call": id}); err != nil {
			log.Printf("IPC write: %v", err)
		}
	} else {
		log.Printf("%s not connected for %s", role, method)
	}
}
func (c *controller) handle(p *peer, e obj) {
	event := str(e["event"])
	switch event {
	case "accepted", "passed", "quick_dispatched":
		request := str(e["request"])
		if request == "" {
			return
		}
		c.mu.Lock()
		if c.cancel != nil {
			c.cancel()
		}
		ctx, cancel := context.WithTimeout(c.ctx, 10*time.Second)
		c.cancel = cancel
		c.request = request
		c.mu.Unlock()
		if event == "accepted" {
			intent := object(e["intent"])
			go c.execute(ctx, request, intent)
		} else {
			cancel()
		}
	case "ready", "online", "quick_hook_ready":
		log.Printf("agent %s", event)
	case "error", "dispatch_error", "quick_error":
		log.Printf("agent error: %s", str(e["error"]))
	case "result":
		if n, ok := e["call"].(float64); ok {
			c.mu.Lock()
			ch := c.pending[uint64(n)]
			c.mu.Unlock()
			if ch != nil {
				select {
				case ch <- e:
				default:
				}
				return
			}
		}
		if e["error"] != nil {
			log.Printf("action failed: %v", e["error"])
		} else {
			data, _ := json.Marshal(e["result"])
			log.Printf("action completed: %s", data)
		}
	}
}
func (c *controller) execute(ctx context.Context, request string, intent obj) {
	kind := str(intent["kind"])
	switch kind {
	case "personal":
		c.rpc("sdk", "openmix", request, "RDTMAK5uy_kset8DisdE7LSD4TNjEVvrKRTmG7a56sY")
		return
	case "mode":
		status, err := c.await(ctx, "sdk", "inspect")
		if err != nil {
			log.Printf("mode status: %v", err)
			return
		}
		paused := path(status, "result", "player", "state") == float64(2)
		if _, err = c.await(ctx, "sdk", "foregroundplayer"); err != nil {
			log.Printf("mode foreground: %v", err)
			return
		}
		time.Sleep(250 * time.Millisecond)
		if _, err = c.await(ctx, "player", "setmode", intent["mode"]); err != nil {
			log.Printf("mode switch: %v", err)
			return
		}
		if paused {
			time.Sleep(500 * time.Millisecond)
			if ctx.Err() == nil {
				c.rpc("sdk", "dispatch", obj{"kind": "pause"})
			}
		}
		log.Printf("player mode requested: %s", str(intent["mode"]))
		return
	case "search", "flow":
		payload, _ := json.Marshal(intent)
		exe, _ := os.Executable()
		cmd := exec.CommandContext(ctx, exe, "--resolve", string(payload))
		// Requests must use the player's UID, so Android applies the same VPN policy.
		if os.Getuid() == 0 {
			uid, err := packageUID(ctx, "app.rvx.android.apps.youtube.music")
			if err != nil {
				log.Printf("network UID: %v", err)
				return
			}
			cmd.SysProcAttr = &syscall.SysProcAttr{Credential: &syscall.Credential{Uid: uint32(uid), Gid: 3003, Groups: []uint32{3003}}}
		}
		output, err := cmd.Output()
		if err != nil {
			if ee, ok := err.(*exec.ExitError); ok {
				log.Printf("catalogue failed: %s", strings.TrimSpace(string(ee.Stderr)))
			} else {
				log.Printf("catalogue failed: %v", err)
			}
			return
		}
		var selection Selection
		if json.Unmarshal(output, &selection) != nil || !videoID.MatchString(selection.ID) {
			log.Printf("invalid catalogue response")
			return
		}
		c.mu.Lock()
		current := c.request == request
		c.mu.Unlock()
		if !current || ctx.Err() != nil {
			return
		}
		c.rpc("sdk", "openvideo", request, selection.ID, selection.Playlist)
		log.Printf("selection opened: %s", selection.Title)
	case "announce":
		if err := c.announce(ctx, request); err != nil {
			log.Printf("announcement failed: %v", err)
		}
	}
}
func packageUID(ctx context.Context, name string) (int, error) {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	data, err := exec.CommandContext(ctx, "/system/bin/cmd", "package", "list", "packages", "-U", name).Output()
	if err != nil {
		return 0, err
	}
	for _, field := range strings.Fields(string(data)) {
		if strings.HasPrefix(field, "uid:") {
			return strconv.Atoi(strings.TrimPrefix(field, "uid:"))
		}
	}
	return 0, fmt.Errorf("package UID unavailable")
}
func (c *controller) accept(conn net.Conn) {
	defer conn.Close()
	conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	scan := bufio.NewScanner(conn)
	scan.Buffer(make([]byte, 8192), 65536)
	if !scan.Scan() {
		return
	}
	var hello obj
	if json.Unmarshal(scan.Bytes(), &hello) != nil {
		return
	}
	token := str(hello["token"])
	if subtle.ConstantTimeCompare([]byte(token), []byte(c.token)) != 1 {
		return
	}
	role := str(hello["role"])
	if role != "sdk" && role != "player" {
		return
	}
	p := &peer{conn: conn}
	c.mu.Lock()
	old := c.peers[role]
	c.peers[role] = p
	c.mu.Unlock()
	if old != nil {
		old.conn.Close()
	}
	defer func() {
		c.mu.Lock()
		if c.peers[role] == p {
			delete(c.peers, role)
		}
		c.mu.Unlock()
	}()
	conn.SetReadDeadline(time.Time{})
	p.send(obj{"authenticated": true, "route": !*observe})
	log.Printf("%s connected", role)
	go func() { time.Sleep(500 * time.Millisecond); c.rpc(role, "inspect") }()
	for scan.Scan() {
		var e obj
		if json.Unmarshal(scan.Bytes(), &e) == nil {
			c.handle(p, e)
		}
	}
	log.Printf("%s disconnected", role)
}
func supervise(ctx context.Context, role, pkg string) {
	for ctx.Err() == nil {
		data, _ := exec.Command("/system/bin/pidof", pkg).Output()
		fields := strings.Fields(string(data))
		if len(fields) == 0 {
			select {
			case <-ctx.Done():
				return
			case <-time.After(2 * time.Second):
				continue
			}
		}
		pid, err := strconv.Atoi(fields[0])
		if err != nil {
			time.Sleep(2 * time.Second)
			continue
		}
		cmd := exec.CommandContext(ctx, filepath.Join(*root, "frida-inject"), "-p", strconv.Itoa(pid), "-s", filepath.Join(*root, role+".js"), "--runtime=qjs")
		cmd.Stdout = serviceLog
		cmd.Stderr = serviceLog
		log.Printf("attaching %s pid=%d", role, pid)
		err = cmd.Run()
		log.Printf("%s injector exited: %v", role, err)
		select {
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Second):
		}
	}
}
func main() {
	flag.Parse()
	if *resolve != "" {
		var intent obj
		if err := json.Unmarshal([]byte(*resolve), &intent); err != nil {
			log.Fatal(err)
		}
		ctx, cancel := context.WithTimeout(context.Background(), 9*time.Second)
		defer cancel()
		result, err := catalogue(ctx, intent)
		if err != nil {
			log.Fatal(err)
		}
		json.NewEncoder(os.Stdout).Encode(result)
		return
	}
	if os.Getuid() != 0 {
		log.Fatal("root required")
	}
	serviceLog = &rotatingLog{path: filepath.Join(*root, "daemon.log")}
	log.SetOutput(serviceLog)
	lock, err := os.OpenFile(filepath.Join(*root, "daemon.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		log.Fatal(err)
	}
	defer lock.Close()
	if syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) != nil {
		log.Fatal("already running")
	}
	token, err := os.ReadFile(filepath.Join(*root, "token"))
	if err != nil || len(strings.TrimSpace(string(token))) < 32 {
		log.Fatal("missing IPC token")
	}
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer cancel()
	c := &controller{peers: map[string]*peer{}, pending: map[uint64]chan obj{}, token: strings.TrimSpace(string(token)), ctx: ctx}
	listener, err := net.Listen("tcp4", "127.0.0.1:27044")
	if err != nil {
		log.Fatal(err)
	}
	defer listener.Close()
	os.WriteFile(filepath.Join(*root, "daemon.pid"), []byte(strconv.Itoa(os.Getpid())), 0600)
	defer os.Remove(filepath.Join(*root, "daemon.pid"))
	go func() {
		<-ctx.Done()
		listener.Close()
		c.mu.Lock()
		for _, p := range c.peers {
			p.conn.Close()
		}
		c.mu.Unlock()
	}()
	var children sync.WaitGroup
	children.Add(2)
	go func() { defer children.Done(); supervise(ctx, "sdk", "com.yandex.io.sdk") }()
	go func() { defer children.Done(); supervise(ctx, "player", "app.rvx.android.apps.youtube.music") }()
	defer func() { cancel(); children.Wait() }()
	log.Printf("station controller started")
	for {
		conn, err := listener.Accept()
		if err != nil {
			return
		}
		go c.accept(conn)
	}
}

func (c *controller) await(ctx context.Context, role, method string, args ...any) (obj, error) {
	c.mu.Lock()
	p := c.peers[role]
	c.call++
	id := c.call
	ch := make(chan obj, 1)
	c.pending[id] = ch
	c.mu.Unlock()
	defer func() { c.mu.Lock(); delete(c.pending, id); c.mu.Unlock() }()
	if p == nil {
		return nil, fmt.Errorf("%s disconnected", role)
	}
	if err := p.send(obj{"method": method, "args": args, "call": id}); err != nil {
		return nil, err
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(3 * time.Second):
		return nil, fmt.Errorf("%s timed out", method)
	case result := <-ch:
		if result["error"] != nil {
			return nil, fmt.Errorf("%s", result["error"])
		}
		return result, nil
	}
}
func (c *controller) announce(ctx context.Context, request string) error {
	result, err := c.await(ctx, "sdk", "inspect")
	if err != nil {
		return err
	}
	metadata := object(path(result, "result", "player"))
	title, artist := str(metadata["title"]), str(metadata["artist"])
	if title == "" || title == "null" {
		return fmt.Errorf("no title")
	}
	speech := title
	if artist != "" && artist != "null" {
		speech = artist + ". " + title
	}
	runes := []rune(speech)
	if len(runes) > 240 {
		speech = string(runes[:240])
	}
	wav, err := os.CreateTemp(*root, "announce-*.wav")
	if err != nil {
		return err
	}
	name := wav.Name()
	wav.Close()
	defer os.Remove(name)
	cmd := exec.CommandContext(ctx, filepath.Join(*root, "espeak-ng"), "--path="+*root, "-v", "ru", "-s", "155", "-w", name, "--", speech)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("synthesis: %v: %s", err, output)
	}
	data, err := os.ReadFile(name)
	if err != nil {
		return err
	}
	if len(data) > 2000000 {
		return fmt.Errorf("speech too long")
	}
	if _, err = c.await(ctx, "sdk", "ttsbegin", request); err != nil {
		return err
	}
	for start := 0; start < len(data); start += 4096 {
		end := start + 4096
		if end > len(data) {
			end = len(data)
		}
		if _, err = c.await(ctx, "sdk", "ttsappend", request, base64.StdEncoding.EncodeToString(data[start:end])); err != nil {
			return err
		}
	}
	_, err = c.await(ctx, "sdk", "ttsplay", request)
	return err
}
