package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

type obj = map[string]any
type Selection struct {
	ID       string `json:"id"`
	Playlist string `json:"playlistId,omitempty"`
	Title    string `json:"title"`
}

var videoID = regexp.MustCompile(`^[A-Za-z0-9_-]{11}$`)
var httpClient = &http.Client{Timeout: 8 * time.Second}

func object(v any) obj {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return obj{}
}
func str(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
func path(v any, keys ...string) any {
	for _, k := range keys {
		v = object(v)[k]
	}
	return v
}

// Walk in a stable display order; arrays retain YouTube's ranking.
func walk(v any, visit func(obj)) {
	switch x := v.(type) {
	case map[string]any:
		visit(x)
		for _, k := range []string{"items", "gridRenderer", "musicNavigationButtonRenderer", "musicImmersiveCarouselShelfRenderer", "contents", "singleColumnSearchResultsRenderer", "tabbedSearchResultsRenderer", "twoColumnSearchResultsRenderer", "tabs", "tabRenderer", "content", "sectionListRenderer", "musicShelfRenderer", "musicPlaylistShelfRenderer", "musicCardShelfRenderer", "musicResponsiveListItemRenderer", "musicTwoRowItemRenderer", "header", "musicDetailHeaderRenderer", "musicImmersiveHeaderRenderer", "musicCarouselShelfRenderer", "singleColumnBrowseResultsRenderer", "twoColumnBrowseResultsRenderer", "primaryContents", "secondaryContents", "itemSectionRenderer", "videoRenderer", "richItemRenderer"} {
			if a, ok := x[k]; ok {
				walk(a, visit)
			}
		}
	case []any:
		for _, a := range x {
			walk(a, visit)
		}
	}
}
func text(v any) string {
	m := object(v)
	if s := str(m["simpleText"]); s != "" {
		return s
	}
	var b strings.Builder
	if a, ok := m["runs"].([]any); ok {
		for _, r := range a {
			b.WriteString(str(object(r)["text"]))
		}
	}
	return b.String()
}
func api(ctx context.Context, method string, payload obj, web bool) (obj, error) {
	host, client, version := "music.youtube.com", "WEB_REMIX", "1."+time.Now().UTC().Format("20060102")+".01.00"
	if web {
		host, client, version = "www.youtube.com", "WEB", "2."+time.Now().UTC().Format("20060102")+".01.00"
	}
	payload["context"] = obj{"client": obj{"clientName": client, "clientVersion": version, "hl": "en", "gl": "US"}}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, "POST", "https://"+host+"/youtubei/v1/"+method+"?prettyPrint=false", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", "https://"+host)
	req.Header.Set("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36")
	r, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return nil, fmt.Errorf("catalogue HTTP %d", r.StatusCode)
	}
	var result obj
	err = json.NewDecoder(io.LimitReader(r.Body, 12<<20)).Decode(&result)
	return result, err
}
func endpoint(v any) (string, string) {
	m := object(v)
	id := str(path(m, "watchEndpoint", "videoId"))
	browse := str(path(m, "browseEndpoint", "browseId"))
	if id == "" {
		id = str(path(m, "watchPlaylistEndpoint", "playlistId"))
	}
	return id, browse
}
func itemIdentity(m obj) (id, browse, title string) {
	id = str(path(m, "playlistItemData", "videoId"))
	e, b := endpoint(m["navigationEndpoint"])
	if id == "" {
		id = e
	}
	browse = b
	title = text(m["title"])
	if cols, ok := m["flexColumns"].([]any); ok && len(cols) > 0 {
		t := object(path(cols[0], "musicResponsiveListItemFlexColumnRenderer", "text"))
		title = text(t)
		if runs, ok := t["runs"].([]any); ok {
			for _, r := range runs {
				e, b = endpoint(object(r)["navigationEndpoint"])
				if id == "" {
					id = e
				}
				if browse == "" {
					browse = b
				}
			}
		}
	}
	if id == "" {
		id = str(path(m, "onTap", "watchEndpoint", "videoId"))
	}
	return
}
func findTrack(data any) (Selection, error) {
	var out Selection
	walk(data, func(m obj) {
		if out.ID != "" {
			return
		}
		id, _, title := itemIdentity(m)
		if videoID.MatchString(id) {
			out = Selection{ID: id, Title: title}
		}
	})
	if out.ID == "" {
		return out, errors.New("no playable track")
	}
	return out, nil
}
func browseSelection(ctx context.Context, browse string) (Selection, error) {
	data, err := api(ctx, "browse", obj{"browseId": browse}, false)
	if err != nil {
		return Selection{}, err
	}
	if strings.HasPrefix(browse, "UC") {
		var artist Selection
		walk(data, func(m obj) {
			if artist.ID != "" || !(strings.EqualFold(text(m["title"]), "Songs") || strings.EqualFold(text(m["title"]), "Top songs")) {
				return
			}
			track, e := findTrack(m)
			if e != nil {
				return
			}
			if b := str(path(m, "title", "navigationEndpoint", "browseEndpoint", "browseId")); strings.HasPrefix(b, "VL") {
				track.Playlist = strings.TrimPrefix(b, "VL")
				artist = track
				return
			}
			if runs, ok := object(m["title"])["runs"].([]any); ok {
				for _, run := range runs {
					_, b := endpoint(object(run)["navigationEndpoint"])
					if strings.HasPrefix(b, "VL") {
						track.Playlist = strings.TrimPrefix(b, "VL")
						artist = track
						break
					}
				}
			}
		})
		if artist.ID != "" {
			return artist, nil
		}
		return Selection{}, fmt.Errorf("artist has no songs collection")
	}
	out, err := findTrack(data)
	if err != nil {
		return out, err
	}
	if strings.HasPrefix(browse, "VL") {
		out.Playlist = strings.TrimPrefix(browse, "VL")
	}
	// Explicit header play/shuffle endpoints retain album or artist queue.
	var scan func(any)
	scan = func(v any) {
		switch x := v.(type) {
		case map[string]any:
			if out.Playlist == "" {
				if s := str(path(x, "watchPlaylistEndpoint", "playlistId")); s != "" {
					out.Playlist = s
				}
				if s := str(path(x, "watchEndpoint", "playlistId")); s != "" {
					out.Playlist = s
				}
			}
			for _, a := range x {
				scan(a)
			}
		case []any:
			for _, a := range x {
				scan(a)
			}
		}
	}
	scan(data)
	return out, nil
}
func catalogue(ctx context.Context, intent obj) (Selection, error) {
	if str(intent["kind"]) == "flow" {
		return mood(ctx, str(intent["mood"]))
	}
	kind, q := str(intent["mediaType"]), str(intent["query"])
	channel := str(intent["channel"])
	if channel != "" || kind == "video" {
		return upload(ctx, q, kind, channel)
	}
	payload := obj{"query": q}
	codes := map[string]string{"song": "II", "album": "IY", "artist": "Ig"}
	if c := codes[kind]; c != "" {
		payload["params"] = "EgWKAQ" + c + "AWoMEA4QChADEAQQCRAF"
	}
	if kind == "playlist" {
		payload["params"] = "Eg-KAQwIABAAGAAgACgBMABqChAEEAMQCRAFEAo%3D"
	}
	data, err := api(ctx, "search", payload, false)
	if err != nil {
		return Selection{}, err
	}
	var id, browse, title string
	walk(data, func(m obj) {
		if id != "" || browse != "" {
			return
		}
		i, b, t := itemIdentity(m)
		if i != "" || b != "" {
			id, browse, title = i, b, t
		}
	})
	if browse != "" && (id == "" || kind == "album" || kind == "artist" || kind == "playlist") {
		return browseSelection(ctx, browse)
	}
	if videoID.MatchString(id) {
		return Selection{ID: id, Title: title}, nil
	}
	if strings.HasPrefix(id, "PL") || strings.HasPrefix(id, "OLAK") {
		return browseSelection(ctx, "VL"+id)
	}
	return upload(ctx, q, kind, channel)
}
func upload(ctx context.Context, q, kind, channel string) (Selection, error) {
	if channel != "" {
		q += " " + channel
	}
	data, err := api(ctx, "search", obj{"query": q}, true)
	if err != nil {
		return Selection{}, err
	}
	var out Selection
	walk(data, func(m obj) {
		if out.ID != "" {
			return
		}
		id := str(m["videoId"])
		if !videoID.MatchString(id) {
			return
		}
		owner := text(m["ownerText"])
		if channel != "" && !strings.Contains(strings.ToLower(owner), strings.ToLower(channel)) {
			return
		}
		if kind == "album" {
			var secs int
			for _, part := range strings.Split(text(m["lengthText"]), ":") {
				var n int
				fmt.Sscanf(part, "%d", &n)
				secs = secs*60 + n
			}
			if secs < 600 {
				return
			}
		}
		out = Selection{ID: id, Title: text(m["title"])}
	})
	if out.ID == "" {
		return out, errors.New("no matching YouTube upload")
	}
	return out, nil
}

func mood(ctx context.Context, name string) (Selection, error) {
	data, err := api(ctx, "browse", obj{"browseId": "FEmusic_moods_and_genres"}, false)
	if err != nil {
		return Selection{}, err
	}
	var params string
	walk(data, func(m obj) {
		if params != "" {
			return
		}
		if strings.EqualFold(text(m["buttonText"]), name) || strings.EqualFold(text(m["title"]), name) {
			params = str(path(m, "clickCommand", "browseEndpoint", "params"))
			if params == "" {
				params = str(path(m, "navigationEndpoint", "browseEndpoint", "params"))
			}
		}
	})
	if params == "" {
		return Selection{}, fmt.Errorf("unknown mood %s", name)
	}
	data, err = api(ctx, "browse", obj{"browseId": "FEmusic_moods_and_genres_category", "params": params}, false)
	if err != nil {
		return Selection{}, err
	}
	var browse string
	walk(data, func(m obj) {
		if browse != "" {
			return
		}
		id, b, _ := itemIdentity(m)
		if strings.HasPrefix(b, "VL") {
			browse = b
		} else if strings.HasPrefix(id, "PL") || strings.HasPrefix(id, "RD") {
			browse = "VL" + id
		}
	})
	if browse == "" {
		return Selection{}, fmt.Errorf("no mood playlist")
	}
	return browseSelection(ctx, browse)
}
