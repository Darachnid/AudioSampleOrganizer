#include "StatusDialog.h"

#include <QAccessible>
#include <QKeyEvent>
#include <QLabel>
#include <QPlainTextEdit>
#include <QShowEvent>
#include <QTextCursor>
#include <QVBoxLayout>

StatusDialog::StatusDialog(QWidget *parent)
    : QDialog(parent)
{
    setModal(true);
    setWindowTitle(QStringLiteral("ClipMark Status"));
    resize(640, 480);

    auto *layout = new QVBoxLayout(this);

    auto *hint = new QLabel(
        QStringLiteral("JAWS status. Press E for brief, Shift+E for detail, Esc to return."),
        this);
    hint->setWordWrap(true);
    hint->setAccessibleName(QStringLiteral("Status dialog instructions"));
    layout->addWidget(hint);

    m_text = new QPlainTextEdit(this);
    m_text->setReadOnly(true);
    m_text->setTabChangesFocus(true);
    m_text->setAccessibleName(QStringLiteral("ClipMark status text"));
    m_text->setAccessibleDescription(
        QStringLiteral("One fact per line for screen reader navigation."));
    layout->addWidget(m_text, 1);

    setAccessibleName(QStringLiteral("ClipMark status dialog"));
}

void StatusDialog::showStatus(const QString &title, const QStringList &lines)
{
    setWindowTitle(title);
    m_text->setPlainText(lines.join(QLatin1Char('\n')));
    m_text->moveCursor(QTextCursor::Start);
    show();
    raise();
    activateWindow();
    m_text->setFocus(Qt::OtherFocusReason);

    QAccessibleEvent focusEvent(m_text, QAccessible::Focus);
    QAccessible::updateAccessibility(&focusEvent);

    QAccessibleEvent nameEvent(m_text, QAccessible::NameChanged);
    QAccessible::updateAccessibility(&nameEvent);
}

void StatusDialog::showEvent(QShowEvent *event)
{
    QDialog::showEvent(event);
    m_text->setFocus(Qt::OtherFocusReason);
}

void StatusDialog::keyPressEvent(QKeyEvent *event)
{
    if (event->key() == Qt::Key_Escape) {
        accept();
        return;
    }

    // Parent MainWindow handles E / Shift+E while this dialog is shown via
    // event filter, or we close on most keys like the curses status view.
    if (event->key() != Qt::Key_E && event->key() != Qt::Key_F1
        && event->key() != Qt::Key_F2) {
        accept();
        return;
    }

    QDialog::keyPressEvent(event);
}
