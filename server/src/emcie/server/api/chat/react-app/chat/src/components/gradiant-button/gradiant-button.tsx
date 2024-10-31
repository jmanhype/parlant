import styles from './gradiant-button.module.scss';
import { ReactElement, ReactNode } from 'react';

interface GradiantButtonProps {
  className?: string;
  buttonClassName?: string;
  children: ReactNode
  onClick: (e: React.MouseEvent) => void;
}

export default function GradiantButton({className, buttonClassName, children, onClick}: GradiantButtonProps): ReactElement {
  return (
    <span tabIndex={0} onClick={onClick} data-testid="gradiant-button" role='button' className={styles.colorsButton + ' relative block rounded-md border-2 border-transparent hover:animate-background-shift ' + (className || '')}>
      <div style={{backgroundSize: '200% 200%'}} className='z-0 absolute top-[-1px] bottom-[-1px] left-[-1px] right-[-1px] animate-background-shift blur-[4px]'></div>
      <span className={buttonClassName + ' ' + styles.children + ' button relative text-center flex justify-center'}>
          {children}
      </span>
    </span>
  );
}