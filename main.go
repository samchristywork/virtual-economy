package main

import (
	"database/sql"
	"fmt"
	"net/http"

	"github.com/mattn/go-sqlite3"
)

type user struct {
	username   string
	registered string
	balance    string
}

func generateUserHTML(users []user) string {
	result := ""
	for _, user := range users {
		fmt.Println(user)
		result += fmt.Sprintf(`<tr>
			<td>%s</td>
			<td>%s</td>
			<td>%s</td>
		</tr>`, user.username, user.registered, user.balance)
	}
	return result
}

func getUsersFromDB(db *sql.DB) []user {
	sqlite3.Version()

	rows, err := db.Query(`
	select users.username, registered, coalesce(balance, 0) from users
	left join balances on users.username = balances.username`)
	if err != nil {
		panic(err.Error())
	}

	var users []user
	for rows.Next() {
		var username, registered, balance string
		err = rows.Scan(&username, &registered, &balance)
		if err != nil {
			panic(err.Error())
		}
		users = append(users, user{username, registered, balance})
	}
	return users
}

func getDB() *sql.DB {
	db, err := sql.Open("sqlite3", "./database.db")
	if err != nil {
		panic(err.Error())
	}
	return db
}

func runSQL(db *sql.DB, sqlStmt string) {
	_, err := db.Exec(sqlStmt)
	if err != nil {
		panic(err.Error())
	}
}

func createUsersTable(db *sql.DB) {
	runSQL(db, `create table if not exists users (
		username text not null primary key,
		registered text not null
	);`)

	runSQL(db, `create table if not exists balances (
		username text not null primary key,
		balance text not null
	);`)
}

func startServer() {
	db := getDB()
	createUsersTable(db)
	users := getUsersFromDB(db)

	fmt.Println("Listening on port 8080")

	http.HandleFunc("/users", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, `<table>
		<thead>
			<tr>
				<th>Username</th>
				<th>Registered</th>
				<th>Balance</th>
			</tr>
		</thead>
		%s
	</table>`, generateUserHTML(users))
	})
	http.HandleFunc("/adduser", func(w http.ResponseWriter, r *http.Request) {
		username := r.FormValue("username")
		registered := r.FormValue("registered")
		balance := r.FormValue("balance")
		fmt.Println(username, registered, balance)
		_, err := db.Exec("insert into users (username, registered, balance) values (?, ?, ?)", username, registered, balance)
		if err != nil {
			//panic(err.Error())
		}
		users = getUsersFromDB(db)
		http.Redirect(w, r, "/users", 301)
	})
	http.Handle("/", http.StripPrefix("/", http.FileServer(http.Dir("static"))))

	http.ListenAndServe(":8080", nil)
}

func main() {
	startServer()
}
