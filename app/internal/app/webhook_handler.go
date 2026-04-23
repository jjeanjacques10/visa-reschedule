package app

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
	"github.com/example/telegram-bot-producer/internal/services"
)

type WebhookHandler struct {
	Repo       services.UserRepository
	Onboarding services.OnboardingService
	Commands   services.CommandService
	Telegram   services.TelegramClient
	Producer   services.SQSProducer
	Logger     *slog.Logger
}

func (h WebhookHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	var upd contracts.TelegramUpdate
	if err := json.NewDecoder(r.Body).Decode(&upd); err != nil || upd.Message == nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	ctx := r.Context()
	chatID := upd.Message.Chat.ID
	text := strings.TrimSpace(upd.Message.Text)
	user, err := h.Repo.GetByChatID(ctx, chatID)
	if err != nil {
		h.Logger.Error("erro repo", "err", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
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
			_, _ = h.Producer.Publish(context.Background(), *user)
		}
	}
	if err != nil {
		h.Logger.Error("erro fluxo", "err", err)
	}
	if reply == "" {
		reply = "Ok"
	}
	_ = h.Telegram.SendMessage(ctx, chatID, reply)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}
