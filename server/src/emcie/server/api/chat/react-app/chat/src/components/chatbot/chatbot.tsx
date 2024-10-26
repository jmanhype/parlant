import { createContext, Dispatch, ReactElement, SetStateAction, useContext, useState } from 'react';
import Chat from '../chat/chat';
import { SessionInterface } from '@/utils/interfaces';
import Sessions from '../sessions/sessions';

interface SessionContext {
    setSessionId: Dispatch<SetStateAction<string | null>>;
    sessionId: string | null;
    setAgentId: Dispatch<SetStateAction<string | null>>;
    agentId: string | null;
    setNewSession: Dispatch<SetStateAction<SessionInterface | null>>;
    newSession: SessionInterface | null;
    sessions: SessionInterface[],
    setSessions: Dispatch<SetStateAction<SessionInterface[]>>;
};

export const SessionProvider = createContext<SessionContext>({
    sessionId: null,
    setSessionId: () => null,
    agentId: null,
    setAgentId: () => null,
    newSession: null,
    setNewSession: () => null,
    sessions: [],
    setSessions: () =>null
});

// eslint-disable-next-line react-refresh/only-export-components
export const useSession = () => useContext(SessionProvider);

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [sessions, setSessions] = useState<SessionInterface[]>([]);
    const [agentId, setAgentId] = useState<string | null>(null);
    const [newSession, setNewSession] = useState<SessionInterface | null>(null);

    return (
        <SessionProvider.Provider value={{sessionId, setSessionId, agentId, setAgentId, newSession, setNewSession, sessions, setSessions}}>
            <div data-testid="chatbot" className="main bg-main h-screen flex flex-col">
                <div className="flex justify-between flex-1 w-full overflow-auto flex-col lg:flex-row">
                    <div className="h-2/5 bg-white lg:h-full pb-4 border-b border-b-gray-900 border-solid w-full lg:border-b-[transparent] lg:w-[308px] lg:border-r">
                        <Sessions />
                    </div>
                    <div className='h-full w-full'>
                        {sessionId && <Chat />}
                    </div>
                </div>
            </div>
        </SessionProvider.Provider>
    );
}