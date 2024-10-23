import { ReactElement, useEffect, useRef, useState } from 'react';
import { Input } from '../ui/input';
import Tooltip from '../ui/custom/tooltip';
import { Button } from '../ui/button';
import { deleteData, patchData } from '@/utils/api';
import { toast } from 'sonner';
import { Check, Edit, Trash, X } from 'lucide-react';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';

interface Props {
    session: SessionInterface;
    isSelected: boolean;
    refetch: () => void;
}

export default function Session({session, isSelected, refetch}: Props): ReactElement {
    const sessionNameRef = useRef<HTMLInputElement>(null);
    const [isEditingTitle, setIsEditingTitle] = useState<boolean>(false);
    const {setSessionId, setAgentId} = useSession();

    useEffect(() => {
        if (!isSelected) return;

        if (session.id === 'NEW_SESSION' && !session.agentId) setAgentId(null);
        else setAgentId('Mr0uvCuu6g');
    }, [isSelected, setAgentId, session]);

    const deleteSession = async (e: React.MouseEvent) => {
        e.stopPropagation();
        return deleteData(`sessions/${session.id}`).then(() => {
            refetch();
            if (isSelected) setSessionId(null);
            toast.success(`Session "${session.title}" deleted successfully`, {closeButton: true});
        }).catch(() => {
            toast.error('Something went wrong');
        });
    };

    const editTitle = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle(true);
        setTimeout(() => sessionNameRef?.current?.select(), 0);
    };

    const saveTitleChange = (e: React.MouseEvent | React.KeyboardEvent) => {
        e.stopPropagation();
        if (sessionNameRef?.current?.value) {
            patchData(`sessions/${session.id}`, {title: sessionNameRef.current.value})
            .then(() => {
                refetch();
                setIsEditingTitle(false);
                toast.success('title changed successfully', {closeButton: true});
            }).catch(() => {
                toast.error('Something went wrong');
            });
        }
    };

    const cancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle(false);
    };

    const onInputKeyUp = (e: React.KeyboardEvent) =>{
        if (e.key === 'Enter') saveTitleChange(e);
    };

    return (
        <div data-testid="session"
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === ' ' && (e.target as HTMLElement).click()}
            onClick={() => setSessionId(session.id)} key={session.id}
            className={'bg-white animate-fade-in duration-500 transition-none text-[14px] font-medium border-b-[0.6px] border-b-solid border-[#EBECF0] cursor-pointer p-1 flex items-center gap-4 justify-between ps-4 h-[80px] ml-4 mr-4 lg:ml-0 lg:mr-0 hover:shadow-xl ' + (isSelected ? '!bg-[#FAF9FF]' : '')}>
            <div className="flex-1 whitespace-nowrap overflow-hidden">
                {!isEditingTitle &&
                    <div className="overflow-hidden overflow-ellipsis">
                        {session.title}
                        <small className='block text-[12px] text-[#A9A9A9] font-light mt-[4px]'>
                            {new Date(session.creation_utc).toLocaleString()}
                        </small>
                    </div>
                }
                {isEditingTitle && <Input data-testid='sessionTitle' ref={sessionNameRef} onKeyUp={onInputKeyUp} onClick={e => e.stopPropagation()} autoFocus defaultValue={session.title} style={{boxShadow: 'none'}} className="bg-[#e2e8f0] text-foreground h-fit p-1 border border-solid border-black"/>}
            </div>
            <div>
                {!isEditingTitle && <Tooltip value='Rename'><Button data-testid="edit" variant='ghost' className="w-[40px] p-0" onClick={editTitle}><Edit/></Button></Tooltip>}
                {!isEditingTitle && <Tooltip value='Delete'><Button data-testid="delete" variant='ghost' className="w-[40px] p-0" onClick={deleteSession}><Trash/></Button></Tooltip>}
                
                {isEditingTitle && <Tooltip value='Cancel'><Button data-testid="cancel" variant='ghost' className="w-[40px] p-0" onClick={cancel}><X/></Button></Tooltip>}
                {isEditingTitle && <Tooltip value='Save'><Button variant='ghost' className="w-[40px] p-0" onClick={saveTitleChange}><Check/></Button></Tooltip>}
            </div>
        </div>
    );
}