package main

import (
	"context"
	"encoding/json"
	"log"
	"os"

	"github.com/example/telegram-bot-producer/internal/app"
	"github.com/example/telegram-bot-producer/internal/config"
	"github.com/example/telegram-bot-producer/internal/integrations"
	"github.com/example/telegram-bot-producer/internal/logger"
)

func main() {
	env, err := config.LoadEnv()
	if err != nil {
		log.Fatal(err)
	}
	repo := &integrations.DynamoDBRepository{Table: env.DynamoDBTable}
	prod := integrations.SQSProducer{QueueURL: env.SQSQueueURL}
	dispatcher := app.ScheduledDispatcher{Repo: repo, Producer: prod, Logger: logger.New()}
	payload, _ := json.Marshal(map[string]any{"source": "visa-rescheduler.scheduler", "detail-type": "dispatch-active-users"})
	if len(os.Args) > 1 {
		payload = []byte(os.Args[1])
	}
	if err := dispatcher.Handle(context.Background(), payload); err != nil {
		log.Fatal(err)
	}
}
