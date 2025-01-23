import {atom} from 'jotai';

export const haveLogs = atom(JSON.parse(localStorage.logs || '{}'));
export const agentsAtom = atom([]);
export const customersAtom = atom([]);
export const sessionIdAtom = atom(null);
export const agentIdIdAtom = atom(null);
export const newSessionAtom = atom(null);
export const sessionsAtom = atom([]);
export const closeDialogAtom = atom(null, (get, set, closeDialog) => {
	if (closeDialog) set(closeDialogAtom, closeDialog);
});
