import { ReactElement, useEffect, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import Session from '../session/session';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';

export const NEW_SESSION_ID = 'NEW_SESSION';
const newSessionObj: SessionInterface = {end_user_id: '', title: 'New Conversation', agentId: '', creation_utc: new Date().toLocaleString(), id: NEW_SESSION_ID};

export default function Sessions(): ReactElement {
    const {sessionId, newSession, setSessionId, setNewSession, setSessions, sessions} = useSession();
    const {data, error, ErrorTemplate, loading, refetch} = useFetch<{sessions: SessionInterface[]}>('sessions');

    const createNewSession = () => {
        setNewSession(newSessionObj);
        setSessionId(newSessionObj.id);
     };

    useEffect(() => {
        if (data?.sessions) setSessions(data.sessions.reverse());
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    useEffect(() => {
        const isNewSession = sessionId && !sessions?.some(s => s.id === sessionId);
        if (isNewSession) refetch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    return (
        <div className="flex flex-col items-center h-full">
            <div role='button' className='min-h-[70px] h-[70px] text-[16px] text-[#213547] font-medium cursor-pointer lg:w-[308px] flex rounded-[6px] border-[10px] border-solid border-white items-center justify-center hover:bg-gray-100'
                onClick={createNewSession}>
                <img src="parlant-bubble.svg" alt="chat bubble" className='pe-2' />
                New Session
            </div>
            <div data-testid="sessions" className="bg-white flex-1 justify-center w-full overflow-auto">
                {ErrorTemplate && <ErrorTemplate />}
                {loading && !sessions?.length && <div>loading...</div>}
                {!error && (newSession ? ([newSession, ...sessions]) :  sessions).map(session => (
                    <Session data-testid="session"
                        isSelected={session.id === sessionId}
                        refetch={refetch}
                        session={session}
                        key={session.id}/>
                ))}
            </div>
        </div>
    );
}