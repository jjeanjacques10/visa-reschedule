package integrations

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type TelegramClient struct {
	BotToken string
	Client   *http.Client
}

type telegramResponse struct {
	OK          bool   `json:"ok"`
	Description string `json:"description"`
}

func (t TelegramClient) SendMessage(_ context.Context, chatID int64, text string) error {
	payload := map[string]any{"chat_id": chatID, "text": text}
	b, _ := json.Marshal(payload)
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", t.BotToken)
	resp, err := t.Client.Post(url, "application/json", bytes.NewReader(b))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var tr telegramResponse
	if err := json.Unmarshal(body, &tr); err != nil {
		return err
	}
	if !tr.OK {
		return fmt.Errorf("telegram erro: %s", tr.Description)
	}
	return nil
}
