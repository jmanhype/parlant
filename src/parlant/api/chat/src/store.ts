import {atom} from 'jotai';
import {AgentInterface, CustomerInterface, SessionInterface} from './utils/interfaces';
import {ReactNode} from 'react';
import {Dimensions} from './hooks/useDialog';

export const haveLogsAtom = atom(JSON.parse(localStorage.logs || '{}'));
export const agentsAtom = atom<AgentInterface[]>([]);
export const customersAtom = atom<CustomerInterface[]>([]);
export const sessionIdAtom = atom<string | null>(null);
export const agentIdIdAtom = atom<string | null>(null);
export const newSessionAtom = atom(null);
export const sessionsAtom = atom<SessionInterface[]>([]);
export const dialogAtom = atom<{openDialog: (title: string | null, content: ReactNode, dimensions: Dimensions, dialogClosed?: () => void) => void; closeDialog: () => void}>({closeDialog: () => null, openDialog: () => null});
