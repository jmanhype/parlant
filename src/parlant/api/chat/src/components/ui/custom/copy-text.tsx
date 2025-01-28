import {Copy} from 'lucide-react';
import {ReactNode} from 'react';
import {toast} from 'sonner';
import {twJoin} from 'tailwind-merge';
import {spaceClick} from '@/utils/methods';
import {fallbackCopyText} from '@/lib/utils';

interface Props {
	text: string;
	textToCopy?: string;
	className?: string;
	element?: HTMLElement;
}

export default function CopyText({text, textToCopy, className, element}: Props): ReactNode {
	if (!textToCopy) textToCopy = text;

	const copyClicked = (e: React.MouseEvent) => {
		e.stopPropagation();
		if (navigator.clipboard && navigator.clipboard.writeText) {
			navigator.clipboard
				.writeText(textToCopy)
				.then(() => toast.info(`Copied text: ${textToCopy}`))
				.catch(() => {
					fallbackCopyText(textToCopy, element);
				});
		} else {
			fallbackCopyText(textToCopy, element);
		}
	};

	return (
		<div className={twJoin('group flex gap-[3px] items-center cursor-pointer', className)} onKeyDown={spaceClick} onClick={copyClicked}>
			<div>{text}</div>
			<div className='hidden group-hover:block' role='button' tabIndex={0}>
				<Copy size={16} />
			</div>
		</div>
	);
}
