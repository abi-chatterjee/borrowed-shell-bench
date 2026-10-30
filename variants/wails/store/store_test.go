package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func ptr(s string) *string { return &s }

func TestSaveListRemove(t *testing.T) {
	s := New(t.TempDir())
	n, err := s.Save(NoteInput{Title: ptr("a"), Body: ptr("b")})
	if err != nil || len(n.ID) != 32 {
		t.Fatalf("save: %v %+v", err, n)
	}
	if got := s.List(); len(got) != 1 || got[0] != n {
		t.Fatalf("list: %+v", got)
	}
	again, err := s.Save(NoteInput{ID: &n.ID, Title: ptr("c")})
	if err != nil || again.Title != "c" || len(s.List()) != 1 {
		t.Fatalf("update: %v %+v", err, again)
	}
	if ok, _ := s.Remove(n.ID); !ok {
		t.Fatal("remove existing")
	}
	if ok, _ := s.Remove(n.ID); ok {
		t.Fatal("remove missing should report false")
	}
}

func TestRejectsBadInputAndSurvivesCorruptFile(t *testing.T) {
	dir := t.TempDir()
	s := New(dir)
	if _, err := s.Save(NoteInput{ID: ptr("../x")}); err == nil {
		t.Fatal("bad id accepted")
	}
	if _, err := s.Save(NoteInput{Body: ptr(strings.Repeat("x", 200000))}); err == nil {
		t.Fatal("oversize body accepted")
	}
	if err := os.WriteFile(filepath.Join(dir, "notes.json"), []byte("{broken"), 0o644); err != nil {
		t.Fatal(err)
	}
	if len(s.List()) != 0 {
		t.Fatal("corrupt file should read as empty")
	}
	if _, err := os.Stat(filepath.Join(dir, "notes.corrupt")); err != nil {
		t.Fatal("corrupt file not kept for inspection")
	}
}

func TestDataDirOverride(t *testing.T) {
	t.Setenv("BENCH_DATA_DIR", "/x/y")
	if DataDir("wails") != "/x/y" {
		t.Fatal("BENCH_DATA_DIR ignored")
	}
}
