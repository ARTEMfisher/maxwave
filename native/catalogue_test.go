package main

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundTrip func(*http.Request) (*http.Response, error)

func (f roundTrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func mockAPI(t *testing.T, responses ...string) {
	t.Helper()
	before := httpClient
	index := 0
	httpClient = &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		if index >= len(responses) {
			t.Fatal("unexpected extra catalogue request")
		}
		s := responses[index]
		index++
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(s)), Header: make(http.Header)}, nil
	})}
	t.Cleanup(func() { httpClient = before })
}
func TestArtistUsesTopSongsCollection(t *testing.T) {
	mockAPI(t, `{"contents":[{"musicResponsiveListItemRenderer":{"navigationEndpoint":{"browseEndpoint":{"browseId":"UCArtist"}},"title":{"runs":[{"text":"Artist"}]}}}]}`, `{"contents":[{"musicShelfRenderer":{"title":{"runs":[{"text":"Top songs","navigationEndpoint":{"browseEndpoint":{"browseId":"VLArtistQueue"}}}]},"contents":[{"musicResponsiveListItemRenderer":{"playlistItemData":{"videoId":"abcdefghijk"},"title":{"runs":[{"text":"Top track"}]}}}]}},{"musicTwoRowItemRenderer":{"navigationEndpoint":{"watchPlaylistEndpoint":{"playlistId":"WrongAlbum"}}}}]}`)
	selected, err := catalogue(context.Background(), obj{"query": "Artist", "mediaType": "artist"})
	if err != nil {
		t.Fatal(err)
	}
	if selected.ID != "abcdefghijk" || selected.Playlist != "ArtistQueue" {
		t.Fatalf("artist replaced by another collection: %#v", selected)
	}
}
func TestChannelAlbumRejectsShortUploadAndWrongChannel(t *testing.T) {
	mockAPI(t, `{"contents":[{"videoRenderer":{"videoId":"short______","ownerText":{"simpleText":"Wanted"},"lengthText":{"simpleText":"1:47"}}},{"videoRenderer":{"videoId":"wrong______","ownerText":{"simpleText":"Other"},"lengthText":{"simpleText":"30:00"}}},{"videoRenderer":{"videoId":"correct____","ownerText":{"simpleText":"Wanted"},"lengthText":{"simpleText":"31:26"},"title":{"simpleText":"Full album"}}}]}`)
	result, err := catalogue(context.Background(), obj{"query": "Album", "mediaType": "album", "channel": "Wanted"})
	if err != nil {
		t.Fatal(err)
	}
	if result.ID != "correct____" {
		t.Fatalf("wrong upload selected: %#v", result)
	}
}
func TestMalformedCatalogueDoesNotInventTrack(t *testing.T) {
	mockAPI(t, `{"contents":[]}`, `{"contents":[]}`)
	if _, err := catalogue(context.Background(), obj{"query": "missing"}); err == nil {
		t.Fatal("empty catalogue must fail")
	}
}
func TestNonSuccessHTTPRejected(t *testing.T) {
	before := httpClient
	defer func() { httpClient = before }()
	httpClient = &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 403, Body: io.NopCloser(strings.NewReader(`{}`))}, nil
	})}
	if _, err := catalogue(context.Background(), obj{"query": "test"}); err == nil {
		t.Fatal("HTTP failure must not become selection")
	}
}
