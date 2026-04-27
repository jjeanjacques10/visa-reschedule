package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/example/telegram-bot-producer/internal/app"
	"github.com/example/telegram-bot-producer/internal/config"
	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/integrations"
	"github.com/example/telegram-bot-producer/internal/logger"
	"github.com/example/telegram-bot-producer/internal/services"
	telebot "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

func main() {
	env, err := config.LoadEnv()
	if err != nil {
		log.Fatal(err)
	}

	repo := &integrations.DynamoDBRepository{Table: env.DynamoDBTable}
	producer := integrations.SQSProducer{QueueURL: env.SQSQueueURL}
	handler := app.WebhookHandler{
		Repo:       repo,
		Onboarding: services.OnboardingService{Repo: repo},
		Commands:   services.CommandService{Repo: repo, Producer: producer},
		Producer:   producer,
		Logger:     logger.New(),
	}

	token := env.TelegramBotToken
	if token == "" {
		log.Fatal("defina a variável de ambiente TELEGRAM_BOT_TOKEN")
	}

	bot, err := telebot.NewBotAPI(token)
	if err != nil {
		log.Fatalf("falha ao criar bot: %v", err)
	}

	updateConfig := telebot.NewUpdate(0)
	updateConfig.Timeout = 60
	updates := bot.GetUpdatesChan(updateConfig)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	log.Printf("bot local iniciado como @%s", bot.Self.UserName)

	for {
		select {
		case <-ctx.Done():
			bot.StopReceivingUpdates()
			return
		case update, ok := <-updates:
			if !ok {
				return
			}
			if update.Message == nil || update.Message.Text == "" {
				continue
			}

			telegramUpdate := contracts.TelegramUpdate{
				UpdateID: int64(update.UpdateID),
				Message: &contracts.TelegramMessage{
					Chat: contracts.TelegramChat{ID: update.Message.Chat.ID},
					Text: update.Message.Text,
				},
			}
			if update.Message.From != nil {
				telegramUpdate.Message.From = &contracts.TelegramFrom{ID: update.Message.From.ID, Username: update.Message.From.UserName}
			}

			chatID, reply, err := handler.ProcessTelegramUpdate(ctx, telegramUpdate)
			if err != nil {
				log.Printf("erro ao processar update do telegram: %v", err)
			}
			if reply == "" {
				continue
			}

			msg := telebot.NewMessage(chatID, reply)
			if _, err := bot.Send(msg); err != nil {
				log.Printf("erro ao responder mensagem: %v", err)
			}
		}
	}
}
