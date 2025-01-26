import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import remarkBreaks from 'remark-breaks';
import styles from '../message/message.module.scss';
import {twJoin} from 'tailwind-merge';

const Markdown = ({children, className}: {children: string; className?: string}) => {
	return (
		<ReactMarkdown rehypePlugins={[rehypeHighlight]} remarkPlugins={[remarkGfm, remarkBreaks]} className={twJoin(styles.markdown, className)}>
			{children}
		</ReactMarkdown>
	);
};

export default Markdown;
