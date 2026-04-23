package logger

import (
	"context"
	"log/slog"
	"os"
)

type contextKey string

const requestIDKey contextKey = "request_id"

func New() *slog.Logger {
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
}

func WithRequestID(ctx context.Context, requestID string) context.Context {
	return context.WithValue(ctx, requestIDKey, requestID)
}

func FromContext(ctx context.Context, base *slog.Logger) *slog.Logger {
	if v := ctx.Value(requestIDKey); v != nil {
		if s, ok := v.(string); ok && s != "" {
			return base.With("request_id", s)
		}
	}
	return base
}
