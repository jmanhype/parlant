import React, { Dispatch, ReactElement, SetStateAction, useEffect, useRef, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Button } from "../ui/button";
import { deleteData, patchData } from "@/utils/api";
import { Check, Edit, Trash, X } from "lucide-react";
import { Input } from "../ui/input";
import Tooltip from "../ui/custom/tooltip";
import { toast } from "sonner";

interface Props {
    agentId: string | undefined;
    setSession: Dispatch<SetStateAction<null | string>>;
    sessionId: string | null;
}

interface Session {
    id: string;
    title: string;
    end_user_id: string;
}

export default function Sessions({agentId, setSession, sessionId}: Props): ReactElement {
    const sessionNameRef = useRef<HTMLInputElement>(null);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isEditingTitle, setIsEditingTitle] = useState<{ [key: string]: boolean }>({});
    const {data, error, ErrorTemplate, loading, refetch} = useFetch<{sessions: Session[]}>('sessions/', {agent_id: agentId}, [agentId]);

    useEffect(() => data?.sessions && setSessions(data.sessions.reverse()), [data]);

    useEffect(() => {
        const isNewSession = sessionId && !sessions?.some(s => s.id === sessionId);
        if (isNewSession) refetch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    const deleteSession = async (e: React.MouseEvent, selectedSession: Session) => {
        e.stopPropagation();
        return deleteData(`sessions/${selectedSession.id}`).then(() => {
            refetch();
            if (selectedSession.id === sessionId) setSession(null);
            toast.success(`Session "${selectedSession.title}" deleted successfully`, {closeButton: true});
        }).catch(() => {
            toast.error('Something went wrong');
        });
    }

    const editTitle = async (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        setIsEditingTitle({[sessionId]: true});
        setTimeout(() => sessionNameRef?.current?.select(), 0);
    }

    const saveTitleChange = (e: React.MouseEvent | React.KeyboardEvent, sessionId: string) => {
        e.stopPropagation();
        if (sessionNameRef?.current?.value) {
            patchData(`sessions/${sessionId}`, {title: sessionNameRef.current.value})
            .then(() => {
                refetch();
                setIsEditingTitle({});
                toast.success('title changed successfully', {closeButton: true});
            }).catch(() => {
                toast.error('Something went wrong');
            });
        }
    };

    const cancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle({});
    };

    const onInputKeyUp = (e: React.KeyboardEvent, sessionId: string) =>{
        if (e.key === 'Enter') saveTitleChange(e, sessionId);
    }

    return (
        <div className="flex justify-center pt-4 flex-col gap-4 w-full lg:w-[80%]">
            {ErrorTemplate && <ErrorTemplate />}
            {loading && <div>loading...</div>}
            {!loading && !error && sessions.map(session => (
                <div data-testid="session" role="button" tabIndex={0} onKeyDown={e => e.key === ' ' && e.target.click()} onClick={() => setSession(session.id)} key={session.id} className={"bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded flex items-center gap-4 justify-between ps-4 h-[50px] ml-4 mr-4 lg:ml-0 lg:mr-0 " + (session.id === sessionId ? '!bg-blue-600 text-white' : '')}>
                    <div className="flex-1 whitespace-nowrap overflow-hidden">
                        {!isEditingTitle[session.id] && <div className="overflow-hidden overflow-ellipsis">{session.title}</div>}
                        {isEditingTitle[session.id] && <Input data-testid='sessionTitle' ref={sessionNameRef} onKeyUp={e => onInputKeyUp(e, session.id)} onClick={e => e.stopPropagation()} autoFocus defaultValue={session.title} style={{boxShadow: 'none'}} className="bg-[#e2e8f0] text-foreground h-fit p-1 border border-solid border-black"/>}
                    </div>
                    <div>
                        {!isEditingTitle[session.id] && <Tooltip value='Edit'><Button variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => editTitle(e, session.id)}><Edit/></Button></Tooltip>}
                        {!isEditingTitle[session.id] && <Tooltip value='Delete'><Button variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => deleteSession(e, session)}><Trash/></Button></Tooltip>}
                        
                        {isEditingTitle[session.id] && <Tooltip value='Cancel'><Button variant='ghost' className="w-[40px] p-0" onClick={cancel}><X/></Button></Tooltip>}
                        {isEditingTitle[session.id] && <Tooltip value='Save'><Button variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => saveTitleChange(e, session.id)}><Check/></Button></Tooltip>}
                    </div>
                </div>
            ))}
        </div>
    )
}