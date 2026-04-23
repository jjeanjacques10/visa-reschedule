package app

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/services"
)

type ScheduledDispatcher struct {
	Repo     services.UserRepository
	Producer services.SQSProducer
	Logger   *slog.Logger
}

func (d ScheduledDispatcher) Handle(ctx context.Context, payload []byte) error {
	var evt contracts.EventBridgeEvent
	if err := json.Unmarshal(payload, &evt); err != nil {
		return err
	}
	if evt.DetailType != "dispatch-active-users" {
		return errors.New("evento invalido")
	}
	var last map[string]string
	for {
		users, next, err := d.Repo.ListActiveUsers(ctx, 25, last)
		if err != nil {
			return err
		}
		for _, u := range users {
			if _, err := d.Producer.Publish(ctx, u); err != nil {
				d.Logger.Error("falha publicacao", "chat_id", u.ChatID, "err", err)
			}
		}
		if next == nil {
			break
		}
		last = next
	}
	return nil
}
