import { Button } from '@/components/ui/button';
import { useSession } from '@/components/chatbot/chatbot';

interface Action {
    text: string;
    onClick: () => void;
    isMainAction?: boolean;
}

export const useQuestionDialog = () => {
    const {openDialog, closeDialog} = useSession();

    const openQuestionDialog = (title: string, question: string, actions: Action[]) => {
        const Content = () => 
            <div className='h-full flex flex-col justify-between ms-[30px] me-[20px]'>
                <p className='mt-[10px]'>{question}</p>
                <div className='h-[80px] flex items-center justify-end'>
                    <Button data-testid="cancel" onClick={closeDialog} className='hover:bg-[#EBE9F5] bg-[#F2F0FC] h-[46px] w-[96px] text-black rounded-[6px] py-[12px] px-[24px] me-[10px] text-[16px] font-normal'>Cancel</Button>
                    {actions.map(action => {
                        if (action.isMainAction) return <Button onClick={action.onClick} className='h-[46px] w-[161px] bg-[#213547] hover:bg-black rounded-[6px] py-[10px] px-[29.5px] text-[15px] font-medium'>{action.text}</Button>;
                        return <Button key={action.text} onClick={action.onClick} className='hover:bg-[#EBE9F5] bg-[#F2F0FC] h-[46px] w-[96px] text-black rounded-[6px] py-[12px] px-[24px] me-[10px] text-[16px] font-normal'>{action.text}</Button>;
                    })}
                </div>
            </div>;
        return openDialog(title, <Content />, {height: '230px', width: '480px'});
    };

    return {openQuestionDialog, closeQuestionDialog: closeDialog};
};