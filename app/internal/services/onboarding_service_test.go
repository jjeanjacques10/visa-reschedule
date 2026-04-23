package services

import (
	"context"
	"testing"

	"github.com/example/telegram-bot-producer/internal/domain"
)

type memRepo struct{ m map[int64]domain.User }

func (r *memRepo) GetByChatID(_ context.Context, chatID int64) (*domain.User, error) {
	u, ok := r.m[chatID]
	if !ok {
		return nil, nil
	}
	return &u, nil
}
func (r *memRepo) GetByPortalUsername(context.Context, string) (*domain.User, error) { return nil, nil }
func (r *memRepo) Save(_ context.Context, u *domain.User) error {
	if r.m == nil {
		r.m = map[int64]domain.User{}
	}
	r.m[u.ChatID] = *u
	return nil
}
func (r *memRepo) DeleteByChatID(_ context.Context, chatID int64) error {
	delete(r.m, chatID)
	return nil
}
func (r *memRepo) ListActiveUsers(context.Context, int32, map[string]string) ([]domain.User, map[string]string, error) {
	return nil, nil, nil
}

func TestOnboardingFlow(t *testing.T) {
	repo := &memRepo{m: map[int64]domain.User{}}
	svc := OnboardingService{Repo: repo}
	u := &domain.User{ChatID: 1, State: domain.StateWaitingEmail}
	steps := []string{"u@test.com", "12345", "2026-09-20", "2026-07-15", "Sao Paulo", "sim"}
	for _, in := range steps {
		_, err := svc.Next(context.Background(), u, in)
		if err != nil {
			t.Fatal(err)
		}
	}
	if u.State != domain.StateActive || !u.MonitoringEnabled {
		t.Fatal("expected active")
	}
}
