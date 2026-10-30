//! Note storage: one JSON file in a per-user data directory (same format as the
//! other variants: {"notes": [{id, title, body, updated}]}).
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_TITLE: usize = 200;
const MAX_BODY: usize = 100_000;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Note {
    pub id: String,
    pub title: String,
    pub body: String,
    pub updated: u64,
}

#[derive(Deserialize, Debug)]
pub struct NoteInput {
    pub id: Option<String>,
    pub title: Option<String>,
    pub body: Option<String>,
}

#[derive(Serialize, Deserialize, Default)]
struct File {
    #[serde(default)]
    notes: Vec<Note>,
}

pub struct Store {
    dir: PathBuf,
}

pub fn now_ms() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

/// Directory for a variant. BENCH_DATA_DIR wins; otherwise the per-OS user data dir.
pub fn data_dir(variant: &str) -> PathBuf {
    if let Some(d) = std::env::var_os("BENCH_DATA_DIR") {
        return PathBuf::from(d);
    }
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_default();
    let base = if cfg!(target_os = "macos") {
        home.join("Library").join("Application Support").join("BenchNotes")
    } else if cfg!(target_os = "windows") {
        std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join("AppData").join("Local"))
            .join("BenchNotes")
    } else {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local").join("share"))
            .join("BenchNotes")
    };
    base.join(variant)
}

fn valid_id(id: &str) -> bool {
    id.len() == 32 && id.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

impl Store {
    pub fn new(dir: impl AsRef<Path>) -> Self {
        Store { dir: dir.as_ref().to_path_buf() }
    }

    fn file(&self) -> PathBuf {
        self.dir.join("notes.json")
    }

    fn load(&self) -> Vec<Note> {
        match fs::read_to_string(self.file()) {
            Ok(text) => match serde_json::from_str::<File>(&text) {
                Ok(f) => f.notes,
                Err(_) => {
                    let _ = fs::rename(self.file(), self.dir.join("notes.corrupt"));
                    Vec::new()
                }
            },
            Err(_) => Vec::new(),
        }
    }

    fn write(&self, notes: &[Note]) -> Result<(), String> {
        fs::create_dir_all(&self.dir).map_err(|e| e.to_string())?;
        let tmp = self.dir.join("notes.json.tmp");
        let json = serde_json::to_string(&serde_json::json!({ "notes": notes })).map_err(|e| e.to_string())?;
        let mut f = fs::File::create(&tmp).map_err(|e| e.to_string())?;
        f.write_all(json.as_bytes()).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        fs::rename(&tmp, self.file()).map_err(|e| e.to_string())
    }

    pub fn list(&self) -> Vec<Note> {
        self.load()
    }

    pub fn save(&self, input: NoteInput) -> Result<Note, String> {
        let title = input.title.unwrap_or_default();
        let body = input.body.unwrap_or_default();
        if title.chars().count() > MAX_TITLE || body.chars().count() > MAX_BODY {
            return Err("note too large".into());
        }
        if let Some(id) = &input.id {
            if !valid_id(id) {
                return Err("bad id".into());
            }
        }
        let id = input.id.unwrap_or_else(|| uuid::Uuid::new_v4().simple().to_string());
        let mut notes = self.load();
        let saved = Note { id: id.clone(), title, body, updated: now_ms() };
        match notes.iter_mut().find(|n| n.id == id) {
            Some(slot) => *slot = saved.clone(),
            None => notes.push(saved.clone()),
        }
        self.write(&notes)?;
        Ok(saved)
    }

    pub fn remove(&self, id: &str) -> Result<bool, String> {
        let notes = self.load();
        let kept: Vec<Note> = notes.iter().filter(|n| n.id != id).cloned().collect();
        if kept.len() == notes.len() {
            return Ok(false);
        }
        self.write(&kept)?;
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("bn-rs-{}-{}", name, now_ms()));
        let _ = fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn save_list_remove() {
        let dir = tmp("crud");
        let s = Store::new(&dir);
        let n = s.save(NoteInput { id: None, title: Some("a".into()), body: Some("b".into()) }).unwrap();
        assert_eq!(n.id.len(), 32);
        assert_eq!(s.list(), vec![n.clone()]);
        let again = s.save(NoteInput { id: Some(n.id.clone()), title: Some("c".into()), body: None }).unwrap();
        assert_eq!(s.list().len(), 1);
        assert_eq!(again.title, "c");
        assert!(s.remove(&n.id).unwrap());
        assert!(!s.remove(&n.id).unwrap());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn rejects_bad_input_and_survives_corrupt_file() {
        let dir = tmp("bad");
        let s = Store::new(&dir);
        assert!(s.save(NoteInput { id: Some("../x".into()), title: None, body: None }).is_err());
        assert!(s.save(NoteInput { id: None, title: None, body: Some("x".repeat(200_000)) }).is_err());
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("notes.json"), "{broken").unwrap();
        assert!(s.list().is_empty());
        assert!(dir.join("notes.corrupt").exists());
        let _ = fs::remove_dir_all(&dir);
    }
}
