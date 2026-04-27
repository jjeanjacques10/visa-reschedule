package integrations

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/example/telegram-bot-producer/internal/contracts"
	"github.com/example/telegram-bot-producer/internal/domain"
)

type SQSProducer struct {
	QueueURL string
}

func (p SQSProducer) Publish(_ context.Context, user domain.User) (contracts.SQSDispatchMessage, error) {
	msg := contracts.SQSDispatchMessage{
		RequestID:              fmt.Sprintf("%d-%d", user.ChatID, time.Now().UnixNano()),
		ClientID:               user.ClientID(),
		TelegramChatID:         strconv.FormatInt(user.ChatID, 10),
		PortalUsername:         user.PortalUsername,
		PortalPassword:         user.EncryptedPassword,
		CurrentAppointmentDate: user.CurrentAppointmentDate,
		DesiredAppointmentDate: user.DesiredAppointmentDate,
		City:                   user.City,
	}
	b, _ := json.Marshal(msg)
	_, _ = os.Stdout.WriteString(string(b) + "\n")
	return msg, nil
}
