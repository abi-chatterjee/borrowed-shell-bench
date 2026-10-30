// Package store keeps notes in one JSON file: {"notes": [{id, title, body, updated}]}.
// Standard library only, same format and limits as the other variants.
package store

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sync"
	"time"
	"unicode/utf8"
)

const (
	maxTitle = 200
	maxBody  = 100000
)

var idRe = regexp.MustCompile(`^[0-9a-f]{32}$`)

type Note struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Body    string `json:"body"`
	Updated int64  `json:"updated"`
}

// NoteInput is what the page sends; absent fields are nil.
type NoteInput struct {
	ID    *string `json:"id"`
	Title *string `json:"title"`
	Body  *string `json:"body"`
}

type Store struct {
	mu  sync.Mutex
	dir string
}

func New(dir string) *Store { return &Store{dir: dir} }

// DataDir returns BENCH_DATA_DIR, or the per-OS user data directory for variant.
func DataDir(variant string) string {
	if d := os.Getenv("BENCH_DATA_DIR"); d != "" {
		return d
	}
	home, _ := os.UserHomeDir()
	var base string
	switch runtime.GOOS {
	case "darwin":
		base = filepath.Join(home, "Library", "Application Support", "BenchNotes")
	case "windows":
		local := os.Getenv("LOCALAPPDATA")
		if local == "" {
			local = filepath.Join(home, "AppData", "Local")
		}
		base = filepath.Join(local, "BenchNotes")
	default:
		xdg := os.Getenv("XDG_DATA_HOME")
		if xdg == "" {
			xdg = filepath.Join(home, ".local", "share")
		}
		base = filepath.Join(xdg, "BenchNotes")
	}
	return filepath.Join(base, variant)
}

func (s *Store) file() string { return filepath.Join(s.dir, "notes.json") }

func (s *Store) load() []Note {
	raw, err := os.ReadFile(s.file())
	if err != nil {
		return []Note{}
	}
	var data struct {
		Notes []Note `json:"notes"`
	}
	if err := json.Unmarshal(raw, &data); err != nil {
		_ = os.Rename(s.file(), filepath.Join(s.dir, "notes.corrupt"))
		return []Note{}
	}
	if data.Notes == nil {
		return []Note{}
	}
	return data.Notes
}

func (s *Store) write(notes []Note) error {
	if err := os.MkdirAll(s.dir, 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(map[string][]Note{"notes": notes})
	if err != nil {
		return err
	}
	tmp := s.file() + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err := f.Write(raw); err != nil {
		f.Close()
		return err
	}
	if err := f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err := f.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, s.file())
}

func (s *Store) List() []Note {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.load()
}

func (s *Store) Save(in NoteInput) (Note, error) {
	title, body := "", ""
	if in.Title != nil {
		title = *in.Title
	}
	if in.Body != nil {
		body = *in.Body
	}
	if utf8.RuneCountInString(title) > maxTitle || utf8.RuneCountInString(body) > maxBody {
		return Note{}, errors.New("note too large")
	}
	id := ""
	if in.ID != nil && *in.ID != "" {
		if !idRe.MatchString(*in.ID) {
			return Note{}, errors.New("bad id")
		}
		id = *in.ID
	}
	if id == "" {
		b := make([]byte, 16)
		if _, err := rand.Read(b); err != nil {
			return Note{}, err
		}
		id = hex.EncodeToString(b)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	notes := s.load()
	saved := Note{ID: id, Title: title, Body: body, Updated: time.Now().UnixMilli()}
	replaced := false
	for i := range notes {
		if notes[i].ID == id {
			notes[i] = saved
			replaced = true
			break
		}
	}
	if !replaced {
		notes = append(notes, saved)
	}
	return saved, s.write(notes)
}

func (s *Store) Remove(id string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	notes := s.load()
	kept := make([]Note, 0, len(notes))
	for _, n := range notes {
		if n.ID != id {
			kept = append(kept, n)
		}
	}
	if len(kept) == len(notes) {
		return false, nil
	}
	return true, s.write(kept)
}
