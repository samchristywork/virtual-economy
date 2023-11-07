package main

import (
	"fmt"
	"net/http"
)

func startServer() {
	fmt.Println("Listening on port 8080")

	http.Handle("/", http.StripPrefix("/", http.FileServer(http.Dir("static"))))

	http.ListenAndServe(":8080", nil)
}

func main() {
	startServer()
}
