// Bench Notes - Wails v2 variant. Backend = bound Go methods on App (frontend/api/wails.js).
package main

import (
	"embed"
	"fmt"
	"os"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:frontend
var assets embed.FS

func main() {
	if os.Getenv("BENCH_SELFTEST") != "" {
		os.Exit(selfTest())
	}
	app := NewApp()
	err := wails.Run(&options.App{
		Title:       "Bench Notes",
		Width:       960,
		Height:      640,
		AssetServer: &assetserver.Options{Assets: assets},
		Bind:        []interface{}{app},
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
