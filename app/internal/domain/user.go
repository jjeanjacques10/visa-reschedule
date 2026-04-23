package domain

import "time"

type User struct {
	ID                     string          `dynamodbav:"id" json:"id"`
	ChatID                 int64           `dynamodbav:"chat_id" json:"chat_id"`
	State                  OnboardingState `dynamodbav:"state" json:"state"`
	MonitoringEnabled      bool            `dynamodbav:"monitoring_enabled" json:"monitoring_enabled"`
	PortalUsername         string          `dynamodbav:"portal_username" json:"portal_username"`
	EncryptedPassword      string          `dynamodbav:"encrypted_password" json:"encrypted_password"`
	CurrentAppointmentDate string          `dynamodbav:"current_appointment_date" json:"current_appointment_date"`
	DesiredAppointmentDate string          `dynamodbav:"desired_appointment_date" json:"desired_appointment_date"`
	City                   string          `dynamodbav:"city" json:"city"`
	UpdatedAt              time.Time       `dynamodbav:"updated_at" json:"updated_at"`
}

func (u User) ClientID() string { return "telegram-" + itoa(u.ChatID) }

func itoa(v int64) string {
	if v == 0 {
		return "0"
	}
	neg := v < 0
	if neg {
		v = -v
	}
	var b [20]byte
	i := len(b)
	for v > 0 {
		i--
		b[i] = byte('0' + v%10)
		v /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
