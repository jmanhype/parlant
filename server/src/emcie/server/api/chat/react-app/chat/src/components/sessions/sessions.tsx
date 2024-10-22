import { ReactElement, useEffect, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import Session from '../session/session';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';

export default function Sessions(): ReactElement {
    const [sessions, setSessions] = useState<SessionInterface[]>([]);
    const {sessionId, agentId} = useSession();
    const {data, error, ErrorTemplate, loading, refetch} = useFetch<{sessions: SessionInterface[]}>('sessions/', {agent_id: agentId}, [agentId]);

    useEffect(() => data?.sessions && setSessions(data.sessions.reverse()), [data]);

    useEffect(() => {
        const isNewSession = sessionId && !sessions?.some(s => s.id === sessionId);
        if (isNewSession) refetch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    return (
        <div data-testid="sessions" className="bg-white flex justify-center flex-col w-full">
            {ErrorTemplate && <ErrorTemplate />}
            {loading && <div>loading...</div>}
            {!loading && !error && sessions.map(session => (
                <Session data-testid="session" isSelected={session.id === sessionId} refetch={refetch} session={session} key={session.id}/>
            ))}
        </div>
    );
}