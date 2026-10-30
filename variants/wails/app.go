package main

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"benchnotes-wails/store"
)

const variant = "wails"

// Listing is what List returns; field names match what frontend/app.js reads.
type Listing struct {
	Variant string       `json:"variant"`
	Version string       `json:"version"`
	Notes   []store.Note `json:"notes"`
}

// App holds the state bound to the frontend.
type App struct {
	store *store.Store
}

func NewApp() *App {
	return &App{store: store.New(store.DataDir(variant))}
}

func (a *App) List() Listing {
	return Listing{Variant: variant, Version: version, Notes: a.store.List()}
}

func (a *App) Save(in store.NoteInput) (store.Note, error) {
	return a.store.Save(in)
}

func (a *App) Remove(id string) (map[string]bool, error) {
	ok, err := a.store.Remove(id)
	return map[string]bool{"ok": ok}, err
}

// Ready is called once by the page after its first render: write epoch ms to BENCH_READY_FILE.
func (a *App) Ready() (map[string]bool, error) {
	if path := os.Getenv("BENCH_READY_FILE"); path != "" {
		tmp := path + ".tmp"
		if err := os.WriteFile(tmp, []byte(strconv.FormatInt(time.Now().UnixMilli(), 10)), 0o644); err != nil {
			return nil, err
		}
		if err := os.Rename(tmp, path); err != nil {
			return nil, err
		}
	}
	return map[string]bool{"ok": true}, nil
}

// selfTest is the headless smoke check: exercise the store, print one line, exit. No window.
func selfTest() int {
	dir, err := os.MkdirTemp("", "bn-wails-selftest-")
	if err != nil {
		fmt.Println("FAILED", err)
		return 1
	}
	defer os.RemoveAll(dir)
	s := store.New(dir)
	title, body := "smoke", "ok"
	n, err := s.Save(store.NoteInput{Title: &title, Body: &body})
	removed, _ := s.Remove(n.ID)
	if err != nil || len(s.List()) != 0 || !removed {
		fmt.Println("FAILED store round trip")
		return 1
	}
	fmt.Printf("OK %s %s\n", variant, version)
	return 0
}
