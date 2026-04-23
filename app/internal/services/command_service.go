package services

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/example/telegram-bot-producer/internal/domain"
)

type CommandService struct {
	Repo     UserRepository
	Producer SQSProducer
}

func (s CommandService) Handle(ctx context.Context, user *domain.User, cmd string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(cmd)) {
	case "/ajuda":
		return "Comandos: /iniciar /status /pausar /retomar /alterar_data /alterar_cidade /parar", nil
	case "/iniciar":
		user.State = domain.StateWaitingEmail
		user.MonitoringEnabled = false
		return "Olá! Vou te ajudar a monitorar vagas. Qual é o email usado no portal AIS?", s.Repo.Save(ctx, user)
	case "/status":
		return fmt.Sprintf("Status: %v | atual=%s | desejada=%s | cidade=%s", user.MonitoringEnabled, user.CurrentAppointmentDate, user.DesiredAppointmentDate, user.City), nil
	case "/pausar":
		user.MonitoringEnabled = false
		user.State = domain.StatePaused
		user.UpdatedAt = time.Now().UTC()
		return "Monitoramento pausado.", s.Repo.Save(ctx, user)
	case "/retomar":
		user.MonitoringEnabled = true
		user.State = domain.StateActive
		user.UpdatedAt = time.Now().UTC()
		if err := s.Repo.Save(ctx, user); err != nil {
			return "", err
		}
		if s.Producer != nil {
			if _, err := s.Producer.Publish(ctx, *user); err != nil {
				return "Falha ao reenfileirar monitoramento.", err
			}
		}
		return "Monitoramento retomado.", nil
	case "/alterar_data":
		user.State = domain.StateWaitingDesiredDate
		return "Informe a nova data desejada (AAAA-MM-DD)", s.Repo.Save(ctx, user)
	case "/alterar_cidade":
		user.State = domain.StateWaitingCity
		return "Informe a nova cidade de consulado.", s.Repo.Save(ctx, user)
	case "/parar":
		if err := s.Repo.DeleteByChatID(ctx, user.ChatID); err != nil {
			return "", err
		}
		return "Configuração removida e monitoramento encerrado.", nil
	default:
		return "Comando não reconhecido. Use /ajuda.", nil
	}
}
