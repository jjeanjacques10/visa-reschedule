package integrations

import (
	"context"
	"sync"
	"time"

	"github.com/example/telegram-bot-producer/internal/domain"
)

type DynamoDBRepository struct {
	Table string
	mu    sync.RWMutex
	byID  map[string]domain.User
}

func (r *DynamoDBRepository) ensure() {
	if r.byID == nil {
		r.byID = map[string]domain.User{}
	}
}

func (r *DynamoDBRepository) GetByChatID(_ context.Context, chatID int64) (*domain.User, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, u := range r.byID {
		if u.ChatID == chatID {
			uc := u
			return &uc, nil
		}
	}
	return nil, nil
}

func (r *DynamoDBRepository) GetByPortalUsername(_ context.Context, username string) (*domain.User, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, u := range r.byID {
		if u.PortalUsername == username {
			uc := u
			return &uc, nil
		}
	}
	return nil, nil
}

func (r *DynamoDBRepository) Save(_ context.Context, user *domain.User) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.ensure()
	if user.ID == "" {
		user.ID = user.ClientID()
	}
	user.UpdatedAt = time.Now().UTC()
	r.byID[user.ID] = *user
	return nil
}

func (r *DynamoDBRepository) DeleteByChatID(_ context.Context, chatID int64) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	for id, u := range r.byID {
		if u.ChatID == chatID {
			delete(r.byID, id)
		}
	}
	return nil
}

func (r *DynamoDBRepository) ListActiveUsers(_ context.Context, limit int32, lastKey map[string]string) ([]domain.User, map[string]string, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var users []domain.User
	var started bool
	if len(lastKey) == 0 {
		started = true
	}
	for id, u := range r.byID {
		if !started {
			if id == lastKey["id"] {
				started = true
			}
			continue
		}
		if u.MonitoringEnabled {
			users = append(users, u)
		}
		if int32(len(users)) >= limit {
			return users, map[string]string{"id": id}, nil
		}
	}
	return users, nil, nil
}
