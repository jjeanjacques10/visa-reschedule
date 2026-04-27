package app

import (
	"bytes"
	"context"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
	"github.com/example/telegram-bot-producer/internal/services"
)

type repoStub struct{ m map[int64]domain.User }

func (r *repoStub) GetByChatID(_ context.Context, chatID int64) (*domain.User, error) {
	u, ok := r.m[chatID]
	if !ok {
		return nil, nil
	}
	return &u, nil
}
func (r *repoStub) GetByPortalUsername(context.Context, string) (*domain.User, error) {
	return nil, nil
}
func (r *repoStub) Save(_ context.Context, u *domain.User) error {
	if r.m == nil {
		r.m = map[int64]domain.User{}
	}
	r.m[u.ChatID] = *u
	return nil
}
func (r *repoStub) DeleteByChatID(_ context.Context, chatID int64) error {
	delete(r.m, chatID)
	return nil
}
func (r *repoStub) ListActiveUsers(context.Context, int32, map[string]string) ([]domain.User, map[string]string, error) {
	return nil, nil, nil
}

type tgStub struct{}

func (tgStub) SendMessage(context.Context, int64, string) error { return nil }

type prodStub struct{}

func (prodStub) Publish(context.Context, domain.User) (contracts.SQSDispatchMessage, error) {
	return contracts.SQSDispatchMessage{}, nil
}

func TestWebhookCommand(t *testing.T) {
	repo := &repoStub{m: map[int64]domain.User{}}
	h := WebhookHandler{Repo: repo, Onboarding: services.OnboardingService{Repo: repo}, Commands: services.CommandService{Repo: repo}, Telegram: tgStub{}, Producer: prodStub{}, Logger: slog.New(slog.NewTextHandler(io.Discard, nil))}
	r := httptest.NewRequest(http.MethodPost, "/webhook/telegram", bytes.NewBufferString(`{"update_id":1,"message":{"chat":{"id":10},"text":"/iniciar"}}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("status %d", w.Code)
	}
}
