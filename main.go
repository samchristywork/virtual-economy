package main

import (
	"database/sql"
	"fmt"
	"github.com/mattn/go-sqlite3"
	"net/http"
)

func getDB() *sql.DB {
	db, err := sql.Open("sqlite3", "./database.db")
	if err != nil {
		panic(err.Error())
	}
	return db
}

func createUsersTable(db *sql.DB) {
	sqlStmt := `
	create table if not exists users (
		username text not null primary key,
		registered text not null,
		balance text not null
	);
	`
	_, err := db.Exec(sqlStmt)
	if err != nil {
		panic(err.Error())
	}
}

func startServer() {
	db := getDB()
	createUsersTable(db)

	fmt.Println("Listening on port 8080")

	http.Handle("/", http.StripPrefix("/", http.FileServer(http.Dir("static"))))

	http.ListenAndServe(":8080", nil)
}

func main() {
	startServer()
}
