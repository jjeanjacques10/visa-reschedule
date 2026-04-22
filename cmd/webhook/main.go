package main

import (
	"log"
	"net/http"
	"time"

	"github.com/example/telegram-bot-producer/internal/app"
	"github.com/example/telegram-bot-producer/internal/config"
	"github.com/example/telegram-bot-producer/internal/integrations"
	"github.com/example/telegram-bot-producer/internal/logger"
	"github.com/example/telegram-bot-producer/internal/services"
)

func main() {
	env, err := config.LoadEnv()
	if err != nil {
		log.Fatal(err)
	}
	lg := logger.New()
	repo := &integrations.DynamoDBRepository{Table: env.DynamoDBTable}
	producer := integrations.SQSProducer{QueueURL: env.SQSQueueURL}
	h := app.WebhookHandler{
		Repo:       repo,
		Onboarding: services.OnboardingService{Repo: repo},
		Commands:   services.CommandService{Repo: repo, Producer: producer},
		Telegram: integrations.TelegramClient{
			BotToken: env.TelegramBotToken,
			Client:   &http.Client{Timeout: 10 * time.Second},
		},
		Producer: producer,
		Logger:   lg,
	}
	http.Handle("/webhook/telegram", h)
	lg.Info("webhook local iniciado", "port", env.HTTPPort)
	log.Fatal(http.ListenAndServe(":"+env.HTTPPort, nil))
}
