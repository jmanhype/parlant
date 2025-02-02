import {atom} from 'jotai';
import {AgentInterface, CustomerInterface, SessionInterface} from './utils/interfaces';
import {ReactNode} from 'react';
import {Dimensions} from './hooks/useDialog';

export const haveLogsAtom = atom(JSON.parse(localStorage.logs || '{}'));
export const agentsAtom = atom<AgentInterface[]>([]);
export const customersAtom = atom<CustomerInterface[]>([]);
export const customerAtom = atom<CustomerInterface | null>(null);
export const sessionAtom = atom<SessionInterface | null>(null);
export const agentAtom = atom<AgentInterface | null>(null);
export const newSessionAtom = atom<SessionInterface | null>(null);
export const sessionsAtom = atom<SessionInterface[]>([]);
export const dialogAtom = atom<{openDialog: (title: string | null, content: ReactNode, dimensions: Dimensions, dialogClosed?: () => void) => void; closeDialog: () => void}>({closeDialog: () => null, openDialog: () => null});
