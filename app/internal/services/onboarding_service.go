package services

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/example/telegram-bot-producer/internal/domain"
)

type OnboardingService struct{ Repo UserRepository }

func (s OnboardingService) Next(ctx context.Context, user *domain.User, text string) (string, error) {
	input := strings.TrimSpace(text)
	switch user.State {
	case "", domain.StatePaused:
		user.State = domain.StateWaitingEmail
		return "Qual é o email usado no portal AIS?", s.Repo.Save(ctx, user)
	case domain.StateWaitingEmail:
		if err := domain.ValidateEmail(input); err != nil {
			return "Email inválido. Digite novamente.", nil
		}
		user.PortalUsername = input
		user.State = domain.StateWaitingPassword
		return "Qual é sua senha?", s.Repo.Save(ctx, user)
	case domain.StateWaitingPassword:
		if len(input) < 4 {
			return "Senha muito curta. Digite novamente.", nil
		}
		user.EncryptedPassword = input
		user.State = domain.StateWaitingCurrentDate
		return "Qual é a data atual da sua entrevista? (AAAA-MM-DD)", s.Repo.Save(ctx, user)
	case domain.StateWaitingCurrentDate:
		if err := domain.ValidateDate(input); err != nil {
			return err.Error(), nil
		}
		user.CurrentAppointmentDate = input
		user.State = domain.StateWaitingDesiredDate
		return "Qual é a data desejada? (AAAA-MM-DD)", s.Repo.Save(ctx, user)
	case domain.StateWaitingDesiredDate:
		if err := domain.ValidateDesiredBeforeCurrent(user.CurrentAppointmentDate, input); err != nil {
			return err.Error(), nil
		}
		user.DesiredAppointmentDate = input
		user.State = domain.StateWaitingCity
		return fmt.Sprintf("Em qual cidade está sua entrevista? (%s)", strings.Join(domain.AllowedCities, ", ")), s.Repo.Save(ctx, user)
	case domain.StateWaitingCity:
		city, ok := domain.NormalizeCity(input)
		if !ok {
			return "Cidade inválida. Escolha uma das opções válidas.", nil
		}
		user.City = city
		user.State = domain.StateWaitingConfirm
		summary := fmt.Sprintf("Resumo:\n- Email: %s\n- Data atual: %s\n- Data desejada: %s\n- Cidade: %s\nDeseja iniciar monitoramento? (sim/não)", user.PortalUsername, user.CurrentAppointmentDate, user.DesiredAppointmentDate, user.City)
		return summary, s.Repo.Save(ctx, user)
	case domain.StateWaitingConfirm:
		if strings.EqualFold(input, "sim") {
			user.State = domain.StateActive
			user.MonitoringEnabled = true
			user.UpdatedAt = time.Now().UTC()
			return "Perfeito! Monitoramento iniciado.", s.Repo.Save(ctx, user)
		}
		if strings.EqualFold(input, "não") || strings.EqualFold(input, "nao") {
			user.MonitoringEnabled = false
			user.State = domain.StatePaused
			return "Tudo bem. Monitoramento pausado.", s.Repo.Save(ctx, user)
		}
		return "Responda com sim ou não.", nil
	default:
		return "Use /ajuda para ver os comandos disponíveis.", nil
	}
}
