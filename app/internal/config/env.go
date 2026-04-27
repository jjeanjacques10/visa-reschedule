package config

import (
	"errors"
	"fmt"
	"os"
)

type Env struct {
	TelegramBotToken string
	SQSQueueURL      string
	DynamoDBTable    string
	AESSecretKey     string
	AWSEndpointURL   string
	AWSRegion        string
	HTTPPort         string
}

func LoadEnv() (Env, error) {
	env := Env{
		TelegramBotToken: os.Getenv("TELEGRAM_BOT_TOKEN"),
		SQSQueueURL:      os.Getenv("SQS_QUEUE_URL"),
		DynamoDBTable:    os.Getenv("DYNAMODB_TABLE"),
		AESSecretKey:     os.Getenv("AES_SECRET_KEY"),
		AWSEndpointURL:   os.Getenv("AWS_ENDPOINT_URL"),
		AWSRegion:        getenvDefault("AWS_REGION", "us-east-1"),
		HTTPPort:         getenvDefault("HTTP_PORT", "8080"),
	}
	if err := validateEnv(env); err != nil {
		return Env{}, err
	}
	return env, nil
}

func validateEnv(env Env) error {
	missing := []string{}
	if env.TelegramBotToken == "" {
		missing = append(missing, "TELEGRAM_BOT_TOKEN")
	}
	if env.SQSQueueURL == "" {
		missing = append(missing, "SQS_QUEUE_URL")
	}
	if env.DynamoDBTable == "" {
		missing = append(missing, "DYNAMODB_TABLE")
	}
	if env.AESSecretKey == "" {
		missing = append(missing, "AES_SECRET_KEY")
	}
	if len(missing) > 0 {
		return fmt.Errorf("variaveis obrigatorias ausentes: %v", missing)
	}
	if len(env.AESSecretKey) < 8 {
		return errors.New("AES_SECRET_KEY deve ter no minimo 8 caracteres")
	}
	return nil
}

func getenvDefault(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
