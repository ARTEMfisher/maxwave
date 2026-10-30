package main

import (
	"os"
	"sync"
)

// Keep at most two 2 MiB logs on the Station, even during a retry loop.
type rotatingLog struct {
	mu   sync.Mutex
	path string
}

func (w *rotatingLog) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if info, e := os.Stat(w.path); e == nil && info.Size()+int64(len(p)) > 2<<20 {
		os.Remove(w.path + ".1")
		if e = os.Rename(w.path, w.path+".1"); e != nil {
			return 0, e
		}
	}
	f, e := os.OpenFile(w.path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if e != nil {
		return 0, e
	}
	defer f.Close()
	return f.Write(p)
}

var serviceLog *rotatingLog
