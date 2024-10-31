import { useState, ReactNode } from 'react';
import { Dialog, DialogContent, DialogHeader } from '@/components/ui/dialog';
import { DialogDescription, DialogTitle } from '@radix-ui/react-dialog';
import { spaceClick } from '@/utils/methods';

type UseDialogReturn = {
  openDialog: (title: string, content: ReactNode, height: string, width: string) => void;
  DialogComponent: () => JSX.Element;
  closeDialog: (e?: React.MouseEvent) => void;
};

export const useDialog = (): UseDialogReturn => {
  const [dialogTitle, setDialogTitle] = useState<ReactNode>(null);
  const [dialogContent, setDialogContent] = useState<ReactNode>(null);
  const [dialogSize, setDialogSize] = useState({height: '', width: ''});

  const openDialog = (title: string, content: ReactNode, height: string, width: string) => {
      setDialogTitle(title);
      setDialogContent(content);
      setDialogSize({height, width});
  };

  const closeDialog = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setDialogContent(null);
    setDialogTitle(null);
  };

  const DialogComponent = () => (
    <Dialog open={!!dialogContent}>
        <DialogContent data-testid="dialog" style={{height: dialogSize.height, width: dialogSize.width}} className={'[&>button]:hidden p-0 h-[536px] font-ubuntu-sans bg-white'}>
                <div className='bg-white rounded-[12px] flex flex-col'>
                    <DialogHeader>
                        <DialogTitle>
                            <div className='h-[68px] w-full flex justify-between items-center ps-[30px] pe-[20px] border-b-[#EBECF0] border-b-[0.6px]'>
                                <DialogDescription className='text-[16px] font-normal'>{dialogTitle}</DialogDescription>
                                <img tabIndex={0} onKeyDown={spaceClick} onClick={closeDialog} className='cursor-pointer rounded-full hover:bg-[#F5F6F8] p-[10px]' src="icons/close.svg" alt="close" height={30} width={30}/>
                            </div>
                        </DialogTitle>
                    </DialogHeader>
                    {dialogContent}
                </div>
            </DialogContent>
    </Dialog>
  );

  return {openDialog, DialogComponent, closeDialog};
};
