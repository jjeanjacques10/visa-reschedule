package app

import (
	"context"
	"fmt"
	"strings"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
	appLogger "github.com/example/telegram-bot-producer/internal/logger"
)

func (h WebhookHandler) ProcessTelegramUpdate(ctx context.Context, upd contracts.TelegramUpdate) (int64, string, error) {
	if upd.Message == nil {
		return 0, "", fmt.Errorf("mensagem ausente")
	}

	log := appLogger.FromContext(ctx, h.Logger)
	chatID := upd.Message.Chat.ID
	text := strings.TrimSpace(upd.Message.Text)

	if log != nil {
		log.Info("telegram update received", "update_id", upd.UpdateID, "chat_id", chatID, "text", text)
	}

	user, err := h.Repo.GetByChatID(ctx, chatID)
	if err != nil {
		if log != nil {
			log.Error("repo lookup failed", "chat_id", chatID, "err", err)
		}
		return chatID, "", err
	}
	if user == nil {
		user = &domain.User{ChatID: chatID, State: domain.StateWaitingEmail}
	}

	var reply string
	if strings.HasPrefix(text, "/") {
		reply, err = h.Commands.Handle(ctx, user, text)
	} else {
		reply, err = h.Onboarding.Next(ctx, user, text)
		if user.State == domain.StateActive && user.MonitoringEnabled && h.Producer != nil {
			_, _ = h.Producer.Publish(ctx, *user)
		}
	}
	if err != nil {
		if log != nil {
			log.Error("telegram flow failed", "chat_id", chatID, "state", user.State, "err", err)
		}
	}
	if reply == "" {
		reply = "Ok"
	}
	if log != nil {
		log.Info("telegram update processed", "chat_id", chatID, "state", user.State, "monitoring_enabled", user.MonitoringEnabled, "reply", reply)
	}
	return chatID, reply, err
}
