import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('ch00-start-here', Article);
export { metadata };
export default Page;
