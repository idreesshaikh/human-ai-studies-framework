export interface SessionAction {
  label: string;
  command: string;
  icon: string;
}

/** The actions offered while a session is recording or paused. */
export function sessionActions(state: { paused: boolean }): SessionAction[] {
  return [
    state.paused
      ? { label: 'Resume session', command: 'tern.resumeSession', icon: 'play' }
      : {
          label: 'Pause session',
          command: 'tern.pauseSession',
          icon: 'debug-pause',
        },
    { label: 'End session', command: 'tern.endSession', icon: 'stop-circle' },
  ];
}
