import { ReactNode, useRef } from "react";
import { useToggleButton } from "react-aria";
import { useToggleState } from "react-stately";
import styles from "./FaqAccordion.module.scss";
import { PlusIcon } from "../Icons";

export type Entry = {
  q: string;
  a: ReactNode;
};

export type Props = {
  entries: Entry[];
};

/**
 * Highlight a selection of questions from the FAQ, allowing people to expand them to see the answers.
 */
export const FaqAccordion = (props: Props) => {
  const entries = props.entries.map((entry) => (
    <QAndA key={entry.q} entry={entry} />
  ));

  return <dl>{entries}</dl>;
};

const QAndA = (props: { entry: Entry }) => {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const state = useToggleState();
  const { buttonProps } = useToggleButton({}, state, buttonRef);

  return (
    <div
      className={`${styles.entry} ${
        state.isSelected ? styles["is-expanded"] : styles["is-collapsed"]
      }`}
    >
      <dt>
        <button {...buttonProps} ref={buttonRef}>
          <span>{props.entry.q}</span>
          <PlusIcon alt="" className={styles["plus-icon"]} />
        </button>
      </dt>
      <dd>{props.entry.a}</dd>
    </div>
  );
};
