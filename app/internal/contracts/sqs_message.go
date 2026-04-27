package contracts

type SQSDispatchMessage struct {
	RequestID              string `json:"request_id"`
	ClientID               string `json:"client_id"`
	TelegramChatID         string `json:"telegram_chat_id"`
	PortalUsername         string `json:"portal_username"`
	PortalPassword         string `json:"portal_password"`
	CurrentAppointmentDate string `json:"current_appointment_date"`
	DesiredAppointmentDate string `json:"desired_appointment_date"`
	City                   string `json:"city"`
}
