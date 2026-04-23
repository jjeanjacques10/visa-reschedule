package services

import (
	"context"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
)

type UserRepository interface {
	GetByChatID(ctx context.Context, chatID int64) (*domain.User, error)
	GetByPortalUsername(ctx context.Context, username string) (*domain.User, error)
	Save(ctx context.Context, user *domain.User) error
	DeleteByChatID(ctx context.Context, chatID int64) error
	ListActiveUsers(ctx context.Context, limit int32, lastKey map[string]string) ([]domain.User, map[string]string, error)
}

type TelegramClient interface {
	SendMessage(ctx context.Context, chatID int64, text string) error
}

type SQSProducer interface {
	Publish(ctx context.Context, user domain.User) (contracts.SQSDispatchMessage, error)
}
