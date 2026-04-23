package domain

type OnboardingState string

const (
	StateWaitingEmail       OnboardingState = "WAITING_EMAIL"
	StateWaitingPassword    OnboardingState = "WAITING_PASSWORD"
	StateWaitingCurrentDate OnboardingState = "WAITING_CURRENT_DATE"
	StateWaitingDesiredDate OnboardingState = "WAITING_DESIRED_DATE"
	StateWaitingCity        OnboardingState = "WAITING_CITY"
	StateWaitingConfirm     OnboardingState = "WAITING_CONFIRMATION"
	StateActive             OnboardingState = "ACTIVE"
	StatePaused             OnboardingState = "PAUSED"
)

func (s OnboardingState) IsValid() bool {
	switch s {
	case StateWaitingEmail, StateWaitingPassword, StateWaitingCurrentDate, StateWaitingDesiredDate, StateWaitingCity, StateWaitingConfirm, StateActive, StatePaused:
		return true
	default:
		return false
	}
}
