import { Dispatch, ReactElement, SetStateAction, useEffect, useRef } from 'react';
import { Input } from '../ui/input';
import Tooltip from '../ui/custom/tooltip';
import { Button } from '../ui/button';
import { deleteData, patchData } from '@/utils/api';
import { toast } from 'sonner';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu';
import { NEW_SESSION_ID } from '../sessions/sessions';
import { getDateStr, getTimeStr } from '@/utils/date';
import styles from './session.module.scss';

interface Props {
    session: SessionInterface;
    isSelected: boolean;
    editingTitle: string | null;
    setEditingTitle: Dispatch<SetStateAction<string | null>>;
    refetch: () => void;
    tabIndex: number;
}

export default function Session({session, isSelected, refetch, editingTitle, setEditingTitle, tabIndex}: Props): ReactElement {
    const sessionNameRef = useRef<HTMLInputElement>(null);
    const {setSessionId, setAgentId, setNewSession} = useSession();

    useEffect(() => {
        if (!isSelected) return;
        document.title = `Parlant | ${session.title}`;

        if (session.id === NEW_SESSION_ID && !session.agent_id) setAgentId(null);
        else setAgentId(session.agent_id);
    }, [isSelected, setAgentId, session.id, session.agent_id, session.title]);

    const deleteSession = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (session.id === NEW_SESSION_ID) {
            setNewSession(null);
            setSessionId(null);
            setAgentId(null);
            return;
        }
        return deleteData(`sessions/${session.id}`).then(() => {
            refetch();
            if (isSelected) {
                setSessionId(null);
                document.title = 'Parlant';
            }
            toast.success(`Session "${session.title}" deleted successfully`, {closeButton: true});
        }).catch(() => {
            toast.error('Something went wrong');
        });
    };

    const editTitle = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setEditingTitle(session.id);
        setTimeout(() => sessionNameRef?.current?.select(), 0);
    };

    const saveTitleChange = (e: React.MouseEvent | React.KeyboardEvent) => {
        e.stopPropagation();
        const title = sessionNameRef?.current?.value;
        if (title) {
            if (session.id === NEW_SESSION_ID) {
                setEditingTitle(null);
                setNewSession(session => session ? {...session, title} : session);
                toast.success('title changed successfully', {closeButton: true});
                return;
            }
            patchData(`sessions/${session.id}`, {title})
            .then(() => {
                setEditingTitle(null);
                refetch();
                toast.success('title changed successfully', {closeButton: true});
            }).catch(() => {
                toast.error('Something went wrong');
            });
        }
    };

    const cancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setEditingTitle(null);
    };

    const onInputKeyUp = (e: React.KeyboardEvent) =>{
        if (e.key === 'Enter') saveTitleChange(e);
    };

    const sessionActions = [
        {title: 'rename', onClick: editTitle, imgPath: 'icons/rename.svg'},
        {title: 'delete', onClick: deleteSession, imgPath: 'icons/delete.svg'},
    ];

    return (
        <div data-testid="session"
            role="button"
            tabIndex={tabIndex}
            onKeyDown={e => e.key === ' ' && (e.target as HTMLElement).click()}
            onClick={() => !editingTitle && setSessionId(session.id)} key={session.id}
            className={'bg-white animate-fade-in text-[14px] font-medium border-b-[0.6px] border-b-solid border-muted cursor-pointer p-1 flex items-center ps-[8px] min-h-[80px] h-[80px] border-r ml-0 mr-0 ' + (editingTitle === session.id ? (styles.editSession + ' !p-[4px_2px] ') : editingTitle ? ' opacity-[33%] ' : ' hover:bg-main ') + (isSelected && editingTitle !== session.id ? '!bg-[#FAF9FF]' : '')}>
            <div className="flex-1 whitespace-nowrap overflow-hidden max-w-[202px] ms-[16px]">
                {editingTitle !== session.id &&
                    <div className="overflow-hidden overflow-ellipsis">
                        {session.title}
                        <small className='text-[12px] text-[#A9A9A9] font-light mt-[4px] flex gap-[6px]'>
                            {getDateStr(session.creation_utc)}
                            <img src="/icons/dot-saparetor.svg" alt="" height={18} width={3}/>
                            {getTimeStr(session.creation_utc)}
                        </small>
                    </div>
                }
                {editingTitle === session.id && 
                    <Input data-testid='sessionTitle'
                        ref={sessionNameRef}
                        onKeyUp={onInputKeyUp}
                        onClick={e => e.stopPropagation()}
                        autoFocus
                        defaultValue={session.title}
                        className="box-shadow-none w-[194px] border-none bg-[#F5F6F8] text-foreground h-fit p-1 ms-[6px]"/>}
            </div>
            <div className='flex items-center gap-[4px]'>
                {editingTitle !== session.id && 
                <DropdownMenu>
                    <DropdownMenuTrigger  disabled={!!editingTitle} data-testid="menu-button" tabIndex={-1} onClick={e => e.stopPropagation()}>
                        <div tabIndex={tabIndex} role='button' className='rounded-full py-2 me-[24px]' onClick={e => e.stopPropagation()}>
                            <img src='/icons/more.svg' alt='more' height={14} width={14}/>
                        </div>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align='start'>
                        {sessionActions.map(sessionAction => (
                            <DropdownMenuItem tabIndex={0} key={sessionAction.title} onClick={sessionAction.onClick} className='gap-0 font-medium text-[14px] font-ubuntu-sans capitalize hover:!bg-[#FAF9FF]'>
                                <img data-testid={sessionAction.title} src={sessionAction.imgPath} height={16} width={18} className='me-[8px]' alt="" />
                                {sessionAction.title}
                            </DropdownMenuItem>
                        ))}
                    </DropdownMenuContent>
                </DropdownMenu>}
                
                {editingTitle == session.id && <Tooltip value='Cancel'><Button data-testid="cancel" variant='ghost' className="w-[28px] h-[28px] p-[8px] rounded-full" onClick={cancel}><img src="/icons/cancel.svg" alt="cancel" /></Button></Tooltip>}
                {editingTitle == session.id && <Tooltip value='Save'><Button variant='ghost' className="w-[28px] h-[28px] p-[8px] rounded-full" onClick={saveTitleChange}><img src="/icons/save.svg" alt="cancel" /></Button></Tooltip>}
            </div>
        </div>
    );
}