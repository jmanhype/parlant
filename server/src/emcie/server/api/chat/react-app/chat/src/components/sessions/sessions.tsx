import { ReactElement, useEffect, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import Session from '../session/session';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';
import VirtualScroll from '../virtual-scroll/virtual-scroll';

export const NEW_SESSION_ID = 'NEW_SESSION';
const newSessionObj: SessionInterface = {
    end_user_id: '',
    title: 'New Conversation',
    agent_id: '',
    creation_utc: new Date().toLocaleString(),
    id: NEW_SESSION_ID
};

export default function Sessions(): ReactElement {
    const [editingTitle, setEditingTitle] = useState<string | null>(null);
    const {sessionId, setSessionId, setNewSession, setSessions, sessions, setAgentId} = useSession();
    const {data, ErrorTemplate, loading, refetch} = useFetch<{sessions: SessionInterface[]}>('sessions');

    const createNewSession = () => {
        setAgentId(null);
        setNewSession(newSessionObj);
        setSessionId(newSessionObj.id);
     };

    useEffect(() => {
        if (data?.sessions) {
            setSessions(data.sessions);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    return (
        <div className="flex flex-col items-center h-full">
            <div className='min-h-[70px] h-[70px] flex justify-center items-center w-[308px] border-b-[0.6px] border-b-solid border-muted'>
                <div tabIndex={1}
                    onKeyUp={(e) => {
                        if (e.key === ' ' || e.key === 'Enter') createNewSession();
                    }}
                    role='button'
                    className='min-h-[50px] h-[50px] py-[10px] text-[16px] text-[#213547] font-medium cursor-pointer w-[288px] flex rounded-[6px] items-center justify-center hover:bg-gray-100'
                    onClick={createNewSession}>
                    <img src="logo.svg" alt="chat bubble" className='pe-2' width={29} height={18}/>
                    New Session
                </div>
            </div>
            <div tabIndex={0} data-testid="sessions" className="bg-white flex-1 justify-center w-full overflow-auto">
            {loading && !sessions?.length && <div>loading...</div>}
            <VirtualScroll height='80px' className='flex flex-col-reverse'>
                {sessions.map((session, i) => (
                    <Session data-testid="session"
                        tabIndex={sessions.length - i}
                        editingTitle={editingTitle}
                        setEditingTitle={setEditingTitle}
                        isSelected={session.id === sessionId}
                        refetch={refetch}
                        session={session}
                        key={session.id}/>
                ))}
            </VirtualScroll>
            {ErrorTemplate && <ErrorTemplate />}
            </div>
        </div>
    );
}