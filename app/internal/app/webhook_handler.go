package app

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"

	"github.com/example/telegram-bot-producer/internal/contracts"
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
	chatID, reply, err := h.ProcessTelegramUpdate(ctx, upd)
	if err != nil && reply == "" {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	_ = h.Telegram.SendMessage(ctx, chatID, reply)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}
