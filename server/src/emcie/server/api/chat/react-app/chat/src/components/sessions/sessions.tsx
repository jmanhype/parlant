import { ReactElement, useEffect, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import Session from '../session/session';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';
import VirtualScroll from '../virtual-scroll/virtual-scroll';

export default function Sessions(): ReactElement {
    const [editingTitle, setEditingTitle] = useState<string | null>(null);
    const {sessionId, setSessions, sessions} = useSession();
    const {data, ErrorTemplate, loading, refetch} = useFetch<{sessions: SessionInterface[]}>('sessions');


    useEffect(() => {
        if (data?.sessions) {
            setSessions(data.sessions);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    return (
        <div className="flex flex-col items-center h-full">
            <div tabIndex={0} data-testid="sessions" className="bg-white flex-1 justify-center w-[332px] overflow-auto">
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