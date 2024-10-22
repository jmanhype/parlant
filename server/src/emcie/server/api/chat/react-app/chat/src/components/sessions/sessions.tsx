import { ReactElement, useEffect, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import Session from '../session/session';
import { useSession } from '../chatbot/chatbot';

interface Props {
    agentId: string | undefined;
}

export interface Session {
    id: string;
    title: string;
    end_user_id: string;
}

export default function Sessions({agentId}: Props): ReactElement {
    const [sessions, setSessions] = useState<Session[]>([]);
    const {data, error, ErrorTemplate, loading, refetch} = useFetch<{sessions: Session[]}>('sessions/', {agent_id: agentId}, [agentId]);
    const {sessionId} = useSession();

    useEffect(() => data?.sessions && setSessions(data.sessions.reverse()), [data]);

    useEffect(() => {
        const isNewSession = sessionId && !sessions?.some(s => s.id === sessionId);
        if (isNewSession) refetch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    return (
        <div data-testid="sessions" className="flex justify-center pt-4 flex-col gap-4 w-full lg:w-[80%]">
            {ErrorTemplate && <ErrorTemplate />}
            {loading && <div>loading...</div>}
            {!loading && !error && sessions.map(session => (
                <Session data-testid="session" isSelected={session.id === sessionId} refetch={refetch} session={session} key={session.id}/>
            ))}
        </div>
    )
}