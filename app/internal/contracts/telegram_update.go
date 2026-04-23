package contracts

type TelegramUpdate struct {
	UpdateID int64            `json:"update_id"`
	Message  *TelegramMessage `json:"message,omitempty"`
}

type TelegramMessage struct {
	MessageID int64         `json:"message_id,omitempty"`
	Chat      TelegramChat  `json:"chat"`
	Text      string        `json:"text,omitempty"`
	From      *TelegramFrom `json:"from,omitempty"`
}

type TelegramChat struct {
	ID int64 `json:"id"`
}

type TelegramFrom struct {
	ID       int64  `json:"id"`
	Username string `json:"username,omitempty"`
}
