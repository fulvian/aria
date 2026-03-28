package main

import (
	"github.com/fulvian/aria/cmd"
	"github.com/fulvian/aria/internal/logging"
)

func main() {
	defer logging.RecoverPanic("main", func() {
		logging.ErrorPersist("Application terminated due to unhandled panic")
	})

	cmd.Execute()
}
