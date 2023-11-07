package main

import (
	"database/sql"
	"fmt"
	"github.com/mattn/go-sqlite3"
	"net/http"
)

func getDB() *sql.DB {
	db, err := sql.Open("sqlite3", "./users.db")
	if err != nil {
		panic(err.Error())
	}
	return db
}

func startServer() {
	db := getDB()

	fmt.Println("Listening on port 8080")

	http.Handle("/", http.StripPrefix("/", http.FileServer(http.Dir("static"))))

	http.ListenAndServe(":8080", nil)
}

func main() {
	startServer()
}
