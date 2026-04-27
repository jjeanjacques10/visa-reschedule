package app

import (
	"context"
	"io"
	"log/slog"
	"testing"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
)

type repoDisp struct{}

func (repoDisp) GetByChatID(context.Context, int64) (*domain.User, error)          { return nil, nil }
func (repoDisp) GetByPortalUsername(context.Context, string) (*domain.User, error) { return nil, nil }
func (repoDisp) Save(context.Context, *domain.User) error                          { return nil }
func (repoDisp) DeleteByChatID(context.Context, int64) error                       { return nil }
func (repoDisp) ListActiveUsers(context.Context, int32, map[string]string) ([]domain.User, map[string]string, error) {
	return []domain.User{{ChatID: 1, PortalUsername: "a", EncryptedPassword: "b", CurrentAppointmentDate: "2026-09-20", DesiredAppointmentDate: "2026-07-15", City: "Sao Paulo"}}, nil, nil
}

type prodDisp struct{ called bool }

func (p *prodDisp) Publish(context.Context, domain.User) (contracts.SQSDispatchMessage, error) {
	p.called = true
	return contracts.SQSDispatchMessage{}, nil
}

func TestDispatcher(t *testing.T) {
	p := &prodDisp{}
	d := ScheduledDispatcher{Repo: repoDisp{}, Producer: p, Logger: slog.New(slog.NewTextHandler(io.Discard, nil))}
	err := d.Handle(context.Background(), []byte(`{"source":"visa-rescheduler.scheduler","detail-type":"dispatch-active-users"}`))
	if err != nil {
		t.Fatal(err)
	}
	if !p.called {
		t.Fatal("expected publish")
	}
}
