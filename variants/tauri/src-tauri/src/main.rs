// Bench Notes - Tauri v2 variant. Backend = Tauri commands (frontend/api/tauri.js).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod store;

use serde::Serialize;
use std::sync::Mutex;
use store::{Note, NoteInput, Store};

const VARIANT: &str = "tauri";
const VERSION: &str = env!("CARGO_PKG_VERSION");

struct AppState {
    store: Mutex<Store>,
}

#[derive(Serialize)]
struct Listing {
    variant: &'static str,
    version: &'static str,
    notes: Vec<Note>,
}

#[tauri::command]
fn list_notes(state: tauri::State<AppState>) -> Result<Listing, String> {
    let store = state.store.lock().map_err(|e| e.to_string())?;
    Ok(Listing { variant: VARIANT, version: VERSION, notes: store.list() })
}

#[tauri::command]
fn save_note(state: tauri::State<AppState>, note: NoteInput) -> Result<Note, String> {
    state.store.lock().map_err(|e| e.to_string())?.save(note)
}

#[tauri::command]
fn remove_note(state: tauri::State<AppState>, id: String) -> Result<serde_json::Value, String> {
    let ok = state.store.lock().map_err(|e| e.to_string())?.remove(&id)?;
    Ok(serde_json::json!({ "ok": ok }))
}

/// Called once by the page after its first render: write epoch ms to BENCH_READY_FILE.
#[tauri::command]
fn ready() -> Result<serde_json::Value, String> {
    if let Some(path) = std::env::var_os("BENCH_READY_FILE") {
        let tmp = std::path::PathBuf::from(&path).with_extension("tmp");
        std::fs::write(&tmp, store::now_ms().to_string()).map_err(|e| e.to_string())?;
        std::fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    }
    Ok(serde_json::json!({ "ok": true }))
}

/// Headless smoke check: exercise the store, print one line, exit. No window.
fn self_test() -> i32 {
    let dir = std::env::temp_dir().join(format!("bn-tauri-selftest-{}", store::now_ms()));
    let s = Store::new(&dir);
    let ok = match s.save(NoteInput { id: None, title: Some("smoke".into()), body: Some("ok".into()) }) {
        Ok(n) => s.list().len() == 1 && s.remove(&n.id).unwrap_or(false) && s.list().is_empty(),
        Err(_) => false,
    };
    let _ = std::fs::remove_dir_all(&dir);
    if ok {
        println!("OK {} {}", VARIANT, VERSION);
        0
    } else {
        println!("FAILED store round trip");
        1
    }
}

fn main() {
    if std::env::var_os("BENCH_SELFTEST").is_some() {
        std::process::exit(self_test());
    }
    tauri::Builder::default()
        .manage(AppState { store: Mutex::new(Store::new(store::data_dir(VARIANT))) })
        .invoke_handler(tauri::generate_handler![list_notes, save_note, remove_note, ready])
        .run(tauri::generate_context!())
        .expect("error while running Bench Notes");
}
