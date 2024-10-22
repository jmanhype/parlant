import { createContext, Dispatch, ReactElement, SetStateAction, useContext, useState } from 'react';
import SessionControl from '../session-control/session-control';
import Chat from '../chat/chat';
import ChatHeader from '../chat-header/chat-header';

interface SessionContext {
    setSessionId: Dispatch<SetStateAction<string | null>>;
    sessionId: string | null;
    setAgentId: Dispatch<SetStateAction<string | null>>;
    agentId: string | null;
};

const SessionProvider = createContext<SessionContext>({
    sessionId: null,
    setSessionId: () => null,
    agentId: null,
    setAgentId: () => null
});

// eslint-disable-next-line react-refresh/only-export-components
export const useSession = () => useContext(SessionProvider);

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [agentId, setAgentId] = useState<string | null>(null);

    return (
        <SessionProvider.Provider value={{sessionId, setSessionId, agentId, setAgentId}}>
            <div data-testid="chatbot" className="main bg-[#FBFBFB] h-screen flex flex-col">
                <ChatHeader />
                <div className="flex justify-between flex-1 w-full overflow-auto flex-col lg:flex-row">
                    <div className="h-2/5 bg-white lg:h-full pb-4 border-b border-b-gray-900 border-solid w-full lg:border-b-[transparent] lg:w-[308px] lg:border-r">
                        <SessionControl />
                    </div>
                    <div className="h-3/5 w-full flex-1 overflow-auto lg:h-full">
                        {sessionId && <Chat />}
                    </div>
                </div>
            </div>
        </SessionProvider.Provider>
    );
}