package app

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
	appLogger "github.com/example/telegram-bot-producer/internal/logger"
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
	log := h.Logger
	if log != nil {
		log.Info("webhook request received", "method", r.Method, "path", r.URL.Path)
	}

	if r.Method != http.MethodPost {
		if log != nil {
			log.Warn("webhook request rejected", "method", r.Method, "path", r.URL.Path, "status", http.StatusMethodNotAllowed)
		}
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	var upd contracts.TelegramUpdate
	if err := json.NewDecoder(r.Body).Decode(&upd); err != nil || upd.Message == nil {
		if log != nil {
			log.Warn("webhook payload invalid", "method", r.Method, "path", r.URL.Path, "err", err)
		}
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	requestID := strings.TrimSpace(r.Header.Get("X-Request-Id"))
	ctx := appLogger.WithRequestID(r.Context(), requestID)
	log = appLogger.FromContext(ctx, h.Logger)
	chatID := upd.Message.Chat.ID
	text := strings.TrimSpace(upd.Message.Text)
	if log != nil {
		log.Info("webhook update received", "update_id", upd.UpdateID, "chat_id", chatID, "text", text)
	}
	user, err := h.Repo.GetByChatID(ctx, chatID)
	if err != nil {
		if log != nil {
			log.Error("repo lookup failed", "chat_id", chatID, "err", err)
		}
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
		if log != nil {
			log.Error("webhook flow failed", "chat_id", chatID, "state", user.State, "err", err)
		}
	}
	if reply == "" {
		reply = "Ok"
	}
	if log != nil {
		log.Info("webhook update processed", "chat_id", chatID, "state", user.State, "monitoring_enabled", user.MonitoringEnabled, "reply", reply)
	}
	_ = h.Telegram.SendMessage(ctx, chatID, reply)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}
